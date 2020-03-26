from logging import getLogger
from typing import Optional, Tuple
from urllib.parse import urlencode

from aiohttp import ClientSession, web

from .models import Authenticator, AuthenticatorException

GITHUB_API = "https://api.github.com"
GITHUB_OAUTH = "https://github.com/login/oauth"
log = getLogger(__name__)

class GitHubAuthenticator(Authenticator):
    name = "github"

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

        self.session = ClientSession()
    
    async def get_register_url(self, callback: str, csrf: str, invite: str) -> str:
        return self.do_get_url(callback, csrf, invite)

    async def get_login_url(self, callback: str, csrf: str) -> str:
        return self.do_get_url(callback, csrf)

    def do_get_url(self, callback: str, csrf: str, invite: str=None) -> str:
        iquery = f"?invite={invite}" if invite else ""
        ruri = callback + iquery
        params = {
            "client_id": self.client_id,
            "redirect_uri": ruri,
            "scope": "read:user",
            "state": csrf
        }

        return f"{GITHUB_OAUTH}/authorize?{urlencode(params)}"

    async def extract_login_callback(self, request: web.Request) -> Tuple[Optional[str], Optional[str]]:
        csrf, uid, *_ = await self.do_extract_callback(request)
        return csrf, uid

    async def extract_register_callback(self, request: web.Request) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        return await self.do_extract_callback(request)

    async def do_extract_callback(self, request: web.Request) -> Tuple[
        Optional[str], Optional[str], Optional[str], Optional[str]
    ]:
        # csrf, uid, name, invite
        csrf = request.query.get("state")
        invite = request.query.get("invite")
        code = request.query.get("code")

        uid, name = await self.get_user_info(code, csrf)
        return csrf, uid, name, invite

    async def get_user_info(self, code: str, csrf: str) -> Tuple[str, str]:
        # uid, name
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "state": csrf
        }
        token = None
        async with self.session.post(
            GITHUB_OAUTH+"/access_token",
            params=params,
            headers={"Accept": "application/json"}
        ) as resp:
            payload = await resp.json()
            if resp.status != 200:
                log.error(f"GitHub API failed: {resp.status} - {payload}")
                raise AuthenticatorException()

            token = payload.get("access_token")

        if not token:
            log.error(f"Failed to get GitHub API token")
            raise AuthenticatorException()

        uid = name = None
        async with self.session.get(
            GITHUB_API+"/user",
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/json"
            }
        ) as resp:
            payload = await resp.json()
            if resp.status != 200:
                log.error(f"Failed to get GitHub user info: {resp.status} - {payload}")
                raise AuthenticatorException()

            uid = str(payload.get("id"))
            name = payload.get("name")

        log.info(f"Authenticated GitHub user: {uid} - {name}")
        return uid, name
