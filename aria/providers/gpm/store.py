from logging import getLogger
from typing import Optional, Sequence

from aiohttp import ClientSession

from aria.database import Database
from aria.models import EntryOverview

from .utils import GPMSong

log = getLogger(__name__)

endpoint = "http://localhost:8080/gpm"

class StoreManager():
    def __init__(self, db_file=None):
        # self.db = db_file or 'config/gpm.sqlite3'
        # self.session = ClientSession()
        self.db = Database()

    async def update(self, songs:Sequence[dict], user:str) -> None:
        try:
            await self.db.update_gpm(songs, user)
            log.info(f"updated GPM for user: {user}")
        except:
            log.error(f"failed to update GPM for user {user}: ", exc_info=True)

    async def search(self, keyword:str):
        payload = None
        try:
            payload = await self.db.search_gpm(keyword)
            return [GPMSong(
                    user=e.get("gpmUser"),
                    song_id=e.get("id"),
                    title=e.get("title"),
                    artist=e.get("artist"),
                    album=e.get("album"),
                    albumArtUrl=e.get("thumbnail"),
                    is_liked=False
            ) for e in payload["results"]]
        except:
            log.error("failed to search GPM: ", exc_info=True)

    async def resolve(self, uri: str) -> Optional[GPMSong]:
        payload = None
        try:
            payload = await self.db.resolve_gpm(uri.strip())
            return GPMSong(
                user=payload["meta"]["gpmUser"],
                song_id=payload["meta"]["id"],
                title=payload["meta"]["title"],
                artist=payload["meta"]["artist"],
                album=payload["meta"]["album"],
                albumArtUrl=payload["meta"]["thumbnail"],
                is_liked=payload["liked"]
            )
        except:
            log.error(f"failed to resolve {uri.strip()}: ", exc_info=True)

    async def cache_store(self, e: EntryOverview):
        try:
            await self.db.store_cache([
                {
                    "provider": e.source,
                    "title": e.title,
                    "url": e.uri,
                    "thumbnail": e.thumbnail,
                    "meta": ""
                }
            ])
        except:
            log.error(f"failed to cache storeTrack {e.title} ({e.uri}): ", exc_info=True)
