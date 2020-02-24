import asyncio
from collections import deque
from logging import getLogger
from pathlib import Path
from random import choice
from typing import Optional

from aiohttp import ClientSession

from aria.database import Database
from aria.models import EntryOverview, PlayableEntry

log = getLogger(__name__)
endpoint = "http://localhost:8080"

class History():
    def __init__(self, view, name):
        self.view = view
        self.name = name
        self.list = deque(maxlen=50)

    def __getattr__(self, _):
        return self.nop

    def nop(self, *_, **__):
        log.error("Operation not permitted on History object!")

    def add_history(self, entry:EntryOverview):
        self.list.appendleft(entry)
        self.view.on_playlists_change()
        self.view.on_playlist_entry_change(self.name)

    async def get_thumbnails(self):
        # deque is a linked list so we do this way
        return [i.entry.thumbnail for i in self.list][:4]

    async def get_entries(self):
        return [i.entry for i in self.list]

    async def get_playable_entries(self):
        return [i for i in self.list]


class PlaylistManager():
    def __init__(self, view, config, provider_manager):
        self.view = view
        self.prov = provider_manager
        self.loop = asyncio.get_event_loop()
        self.lock = asyncio.Lock()
        self.db = Database()

        self.likes = None # special playlist
        self.history = History(self.view, 'History')

    async def get_playlists(self):
        pls = None
        try:
            pls = await self.db.get_playlists()
        except:
            log.error("failed to get playlists: ", exc_info=True)

        return pls

    async def get_likes(self, entries=True):
        likes = None
        try:
            likes = await self.db.get_likes()
            del likes["id"]
            if not entries:
                likes["entries"] = None
        except:
            log.error("failed to get likes: ", exc_info=True)

        return likes

    async def enclose_playlists(self):
        lists = await self.get_playlists()
        likes = await self.get_likes(entries=False)
        for l in lists["playlists"]:
            del l["id"]

        ret = [
            likes,
            {
                'name': self.history.name,
                'length': len(self.history.list),
                'thumbnails': await self.history.get_thumbnails() 
            },
            *lists["playlists"]
        ]

        return ret

    async def get_playlist(self, name:str):
        playlist = None
        try:
            playlist = await self.db.get_playlist(name)
            del playlist["id"]
            playlist["thumbnails"] = playlist["thumbnails"][:5]
            for e in playlist["entries"]:
                del e["meta"]
        except:
            log.error(f"failed to get playlist {name}: ", exc_info=True)

        return playlist

    async def like(self, uri):
        try:
            await self.db.toggle_like(uri, True)
            log.info(f"liked: {uri}")
        except:
            log.error(f"failed to like {uri}: ", exc_info=True)
            return

        self.view.on_playlists_change()
        self.view.on_playlist_entry_change("Likes")

    async def dislike(self, uri):
        try:
            await self.db.toggle_like(uri, False)
            log.info(f"disliked: {uri}")
        except:
            log.error(f"failed to dislike {uri}: ", exc_info=True)
            return

        self.view.on_playlists_change()
        self.view.on_playlist_entry_change("Likes")

    async def create(self, name:str):
        # sanitize name
        name = Path(name).name
        log.info(f'Requested name: {name}')
        if not name:
            return

        try:
            await self.db.create_playlist(name)
            log.info(f"created playlist: {name}")
        except:
            log.error(f"failed to create playlist {name}: ", exc_info=True)
            return
        
        self.view.on_playlists_change()

    async def delete(self, name:str):
        if name in ['Likes', 'History']:
            log.error('You cannot delete Likes list!!!')
            return

        try:
            await self.db.delete_playlist(name)
            log.info(f"deleted playlist: {name}")
        except:
            log.error(f"failed to delete playlist {name}: ", exc_info=True)
            return

        self.view.on_playlists_change()

    async def add_to_playlist(self, name, entries):
        uris = [e.uri for e in entries]
        try:
            await self.db.add_to_playlist(name, uris)
            log.info(f"added {len(uris)} songs to {name}")
        except:
            log.error(f"failed to add songs to {name}: ", exc_info=True)
            return

        self.view.on_playlists_change()
        self.view.on_playlist_entry_change(name)

    async def remove_from_playlist(self, name, uri):
        try:
            await self.db.delete_from_playlist(name, uri)
            log.info(f"deleted {uri} from {name}")
        except:
            log.error(f"failed to delete {uri} from {name}: ", exc_info=True)
            return

        self.view.on_playlists_change()
        self.view.on_playlist_entry_change(name)

    async def is_liked(self, uri):
        payload = None
        try:
            payload = await self.db.is_liked(uri)
        except:
            log.error("failed to get liked state: ", exc_info=True)

        return payload.get("liked") if payload else False

    async def get_random_entry(self) -> Optional[PlayableEntry]:
        likes = await self.get_likes()
        entries = likes.get("entries")
        if len(entries):
            return choice(entries)["uri"]
