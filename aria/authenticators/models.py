from typing import Dict, Optional, Tuple
from aiohttp import web

class Authenticator():
    name: str
    
    async def get_register_url(self, callback:str, csrf:str, invite:str) -> str:
        raise NotImplementedError()

    async def get_login_url(self, callback:str, csrf:str) -> str:
        raise NotImplementedError()

    async def extract_register_callback(self, request:web.Request) -> Tuple[
        Optional[str], Optional[str], Optional[str], Optional[str]
    ]:
        # csrf, uid, name, invite
        raise NotImplementedError()

    async def extract_login_callback(self, request:web.Request) -> Tuple[
        Optional[str], Optional[str]
    ]:
        # csrf, uid
        raise NotImplementedError()

class AuthenticatorException(Exception):
    pass
