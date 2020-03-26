import asyncio
from logging import getLogger
import secrets
from typing import Dict, Optional, Tuple

from aiohttp import web
import aioredis
from tortoise import Tortoise

from aria.authenticators import AUTHENTICATORS
from aria.authenticators.models import Authenticator

from .models import Auth, Token, User

INVITE_LENGTH = 30
INVITE_EXPIRE_DAYS = 7
INVITE_EXPIRE_SECONDS = INVITE_EXPIRE_DAYS*24*60*60
CSRF_EXPIRE_SECONDS = 600
TOKEN_LENGTH = 50
TOKEN_EXPIRE_DAYS = 7
TOKEN_EXPIRE_SECONDS = TOKEN_EXPIRE_DAYS*24*60*60

log = getLogger(__name__)

class AuthenticateManager():
    def __init__(self, config) -> None:
        self.config = config

        self.providers: Dict[str, Authenticator] = {}
        self.init_providers()

        self.redis = None
        # unsafe, it's better using lock/event to ensure redis is initialized
        # but now, it may works...
        asyncio.ensure_future(self.async_init())

    async def async_init(self) -> None:
        await self.init_redis()
        await self.init_db()
        
    async def init_redis(self) -> None:
        self.redis = await aioredis.create_redis_pool(
            self.config.redis_endpoint,
            encoding="utf-8"
        )

    async def init_db(self) -> None:
        await Tortoise.init(
            db_url=self.config.token_db,
            modules={
                "models": [ "aria.auth.models" ]
            }
        )
        await Tortoise.generate_schemas()
       
    def init_providers(self) -> None:
        for prov in AUTHENTICATORS:
            conf = self.config.authenticators_config.get(prov.name) or {}
            try:
                self.providers[prov.name] = prov(**conf)
                log.info(f"Authenticator initialized: {prov.name}")
            except:
                log.error(f"Failed to initialize authenticator {prov.name}: ", exc_info=True)

    # /auth?invite=...
    async def get_is_valid_invite(self, request:web.Request) -> None:
        """
        Check invite code is valid or not

        Returns
        -------
        HTTP status code
        200 if valid
        403 if invalid
        """
        invite = request.query.get("invite")
        if not invite:
            raise web.HTTPBadRequest()

        if await self.is_valid_invite(invite):
            return web.Response()
        else:
            raise web.HTTPForbidden()

    # /auth/{provider}/register?invite=...
    async def get_register_url(self, request:web.Request) -> None:
        """
        Check invite and provider, then redirect to third party login page

        Returns
        -------
        HTTP status code
        302 with redirect
        login page if provider and invite is valid
        web_location if either provider or invite is invalid
        """
        invite = request.query.get("invite")
        if not invite:
            log.error("No invite in register request")
            raise web.HTTPFound(self.config.web_location)
        if not await self.is_valid_invite(invite):
            log.error(f"Invalid invite code: {invite}")
            raise web.HTTPFound(self.config.web_location)

        pname = request.match_info.get("provider")
        if not pname:
            log.error("Invalid path (provider)")
            raise web.HTTPFound(self.config.web_location)
        provider = self.providers.get(pname)
        if not provider:
            log.error(f"Authentication provider not found for: {pname}")
            raise web.HTTPFound(self.config.web_location)
        
        url = None
        csrf = await self.get_csrf()
        try:
            url = await provider.get_register_url(
                f"{self.config.server_location}/auth/{provider.name}/register/callback",
                csrf,
                invite
            )
        except:
            log.error(f"Failed to get register url from provider {provider.name}: ", exc_info=True)
            await self.consume_csrf(csrf)
            raise web.HTTPFound(self.config.web_location)

        if not url:
            log.error(f"Provider {pname} did not return url")
            raise web.HTTPFound(self.config.web_location)

        raise web.HTTPFound(url)
        
    # /auth/{provider}/login
    async def get_login_url(self, request:web.Request) -> None:
        """
        Check provider, then redirect to third party login page

        Returns
        -------
        HTTP status code
        302 with redirect
        login page if provider is valid
        web_location if invalid
        """
        # TODO: this is actual a code clone. Let it gone.
        pname = request.match_info.get("provider")
        if not pname:
            log.error("Invalid path (provider)")
            raise web.HTTPFound(self.config.web_location)
        provider = self.providers.get(pname)
        if not provider:
            log.error(f"Authentication provider not found for: {pname}")
            raise web.HTTPFound(self.config.web_location)

        url = None
        csrf = await self.get_csrf()
        try:
            url = await provider.get_login_url(
                f"{self.config.server_location}/auth/{provider.name}/login/callback",
                csrf
            )
        except:
            log.error(f"Failed to get login url from provider {provider.name}: ", exc_info=True)
            await self.consume_csrf(csrf)
            raise web.HTTPFound(self.config.web_location)

        if not url:
            log.error(f"Provider {pname} did not return url")
            raise web.HTTPFound(self.config.web_location)

        raise web.HTTPFound(url)

    # /auth/{provider}/register/callback
    async def get_register_callback(self, request:web.Request) -> None:
        """
        Callback called from third party authenticator.

        Returns
        -------
        HTTP status code
        302 with redirect
        web_location with Set-Cookie if register successful
        web_location if something went wrong
        """
        pname = request.match_info.get("provider")
        if not pname:
            log.error("Invalid path (provider)")
            raise web.HTTPFound(self.config.web_location)
        provider = self.providers.get(pname)
        if not provider:
            log.error(f"Authentication provider not found for: {pname}")
            raise web.HTTPFound(self.config.web_location)
        
        csrf = uid = invite = None
        try:
            csrf, uid, name, invite = await provider.extract_register_callback(request)
        except:
            log.error(f"Extract register callback failed in provider {provider.name}: ", exc_info=True)
            raise web.HTTPFound(self.config.web_location)

        if not csrf or not await self.consume_csrf(csrf):
            log.error(f"Invalid csrf: {csrf} (provider: {provider.name}")
            raise web.HTTPFound(self.config.web_location)

        # TODO: upgrade to login if uid is found
        if not uid or await self.get_auth(provider.name, uid) != None:
            log.error(f"No uid is given, or user already exists (provider: {provider.name}, uid: {uid})")
            raise web.HTTPFound(self.config.web_location)

        if not invite or not await self.consume_invite(invite):
            log.error(f"No invite is given, or invalid invite (provider: {provider.name}, invite: {invite})")
            raise web.HTTPFound(self.config.web_location)

        await self.register_user(provider.name, uid, name, invite)
        token = await self.get_token()
        resp = web.Response(status=302, headers={
            "Location": self.config.web_location
        })
        resp.set_cookie("token", token, secure=True, max_age=TOKEN_EXPIRE_SECONDS, domain=self.config.domain)
        return resp

    # /auth/{provider}/login/callback
    async def get_login_callback(self, request:web.Request) -> None:
        """
        Callback
        """
        pname = request.match_info.get("provider")
        if not pname:
            log.error("Invalid path (provider)")
            raise web.HTTPFound(self.config.web_location)
        provider = self.providers.get(pname)
        if not provider:
            log.error(f"Authentication provider not found for: {pname}")
            raise web.HTTPFound(self.config.web_location)

        csrf = uid = None
        try:
            csrf, uid = await provider.extract_login_callback(request)
        except:
            log.error(f"Extract login callback failed in provider {provider.name}: ", exc_info=True)
            raise web.HTTPFound(self.config.web_location)

        if not csrf or not await self.consume_csrf(csrf):
            log.error(f"Invalid csrf: {csrf} (provider: {provider.name})")
            raise web.HTTPFound(self.config.web_location)

        if not uid or await self.get_auth(provider.name, uid) == None:
            log.error(f"No uid is given, or user is not found (provider: {provider.name}, uid: {uid})")
            raise web.HTTPFound(self.config.web_location)

        token = await self.get_token()
        resp = web.Response(status=302, headers={
            "Location": self.config.web_location
        })
        resp.set_cookie("token", token, secure=True, max_age=TOKEN_EXPIRE_SECONDS, domain=self.config.domain)
        return resp

    async def register_user(self, prov:str, uid:str, name:Optional[str], invite:str):
        user = User(name=name, invite=invite)
        await user.save()
        auth = Auth(id=f"{prov}:{uid}", user=user)
        await auth.save()
        
    async def is_valid_invite(self, invite:str) -> bool:
        return (await self.redis.exists(f"invite:{invite}")) == 1

    async def get_invite(self) -> str:
        invite = secrets.token_urlsafe(INVITE_LENGTH)
        await self.redis.setex(f"invite:{invite}", INVITE_EXPIRE_SECONDS, 0)
        return invite

    async def consume_invite(self, invite:str) -> bool:
        return await self.redis.delete(f"invite:{invite}") == 1

    async def is_valid_csrf(self, csrf:str) -> bool:
        return (await self.redis.exists(f"csrf:{csrf}")) == 1

    async def get_csrf(self) -> str:
        csrf = secrets.token_urlsafe()
        await self.redis.setex(f"csrf:{csrf}", CSRF_EXPIRE_SECONDS, 0)
        return csrf

    async def consume_csrf(self, csrf:str) -> bool:
        # WHY there's `delete` func? Redis only has `DEL` command!
        return await self.redis.delete(f"csrf:{csrf}") == 1
    
    async def get_token(self, persist=False) -> str:
        token = secrets.token_urlsafe(TOKEN_LENGTH)
        await self.redis.setex(f"token:{token}", TOKEN_EXPIRE_SECONDS, 0)
        if persist:
            await Token(id=token).save()

        return token

    async def is_valid_token(self, token:str, prolong:bool=False):
        if (await self.redis.exists(f"token:{token}")) == 1:
            if prolong:
                asyncio.ensure_future(self.redis.expire(f"token:{token}", TOKEN_EXPIRE_SECONDS))
            return True
        elif await Token.get_or_none(token=token):
            asyncio.ensure_future(self.redis.setex(f"token:{token}", TOKEN_EXPIRE_SECONDS, 0))
            return True

        return False

    async def revoke_token(self) -> bool:
        # TODO
        raise NotImplementedError()

    async def get_auth(self, provider:str, uid:str) -> Optional[Auth]:
        return await Auth.get_or_none(id=f"{provider}:{uid}")
