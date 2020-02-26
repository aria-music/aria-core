from functools import partialmethod
from logging import getLogger
from typing import Any, Optional, Sequence

from aiohttp import ClientSession

log = getLogger(__name__)

class DatabaseError(Exception):
    pass

class Database():
    ins = None
    init = False

    def __new__(cls, endpoint:str=None) -> Any:
        if not cls.ins:
            cls.ins = super().__new__(cls)

        return cls.ins

    def __init__(self, endpoint:str=None) -> None:
        if Database.init:
            return
        
        Database.init = True
        self.sesison = ClientSession() # TOOD: do timeout
        self.endpoint = endpoint
        log.debug(f"endpoint set to {self.endpoint}")

    async def perform(self, method:str, endpoint:str, *, params:dict=None, json:dict=None) -> Optional[dict]:
        log.debug(f"{method} {endpoint}, params: {params}, json: {json}")
        async with self.sesison.request(method, f"{self.endpoint}{endpoint}", params=params, json=json) as resp:
            payload = await resp.json(content_type=None)
            log.debug(f"{resp.status} {resp.reason}")

            if resp.status == 200:
                return payload
            else:
                log.error(f"DB failed: {payload}")
                raise DatabaseError()

    get = partialmethod(perform, "GET")
    post = partialmethod(perform, "POST")
    delete = partialmethod(perform, "DELETE")

    async def get_playlists(self) -> Optional[dict]:
        return await self.get("/playlist")

    async def get_playlist(self, name:str, *, limit:int=1000) -> Optional[dict]:
        return await self.get(f"/playlist/{name}", params={"limit": limit})

    async def create_playlist(self, name:str) -> None:
        await self.post("/playlist", params={"name": name})

    async def delete_playlist(self, name:str) -> None:
        await self.delete(f"/playlist", params={"name": name})

    async def add_to_playlist(self, name:str, uris:Sequence[str]) -> None:
        await self.post(f"/playlist/{name}", json={"entries": uris})

    async def delete_from_playlist(self, name:str, uri:str) -> None:
        await self.delete(f"/playlist/{name}", params={"uri": uri})

    async def get_likes(self, limit:int=1000) -> Optional[dict]:
        return await self.get("/likes", params={"limit": limit})

    async def toggle_like(self, uri:str, like:bool) -> None:
        await self.post("/likes", params={"uri": uri, "like": 1 if like else 0})

    async def is_liked(self, uri:str) -> Optional[dict]:
        return await self.get("/likes/resolve", params={"uri": uri})

    async def get_cache(self, uri:str) -> Optional[dict]:
        return await self.get("/cache", params={"uri": uri})

    async def store_cache(self, entries:Sequence[dict]) -> None:
        await self.post("/cache", json={"entries": entries})

    async def update_gpm(self, entries:Sequence[dict], user:str) -> None:
        await self.post("/gpm/update", params={"name": user}, json={"entries": entries})

    async def search_gpm(self, query:str, *, limit=100) -> Optional[dict]:
        return await self.get("/gpm/search", params={"limit": limit, "query": query})

    async def resolve_gpm(self, uri:str) -> Optional[dict]:
        return await self.get("/gpm", params={"uri": uri})
    
# Database()
