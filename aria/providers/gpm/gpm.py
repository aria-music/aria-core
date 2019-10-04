import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from logging import getLogger
from pathlib import Path
from typing import Optional, Sequence, Union

from aiohttp import ClientSession
from gmusicapi.clients import Mobileclient

from aria.models import EntryOverview, PlayableEntry, Provider
from aria.utils import get_duration, get_volume, save_file

from .store import StoreManager
from .utils import GPMError, GPMSong, get_song_uri, uri_to_id, uri_to_user

log = getLogger(__name__)


class GPMEntry(PlayableEntry):
    def __init__(self, cache_dir, gpm:'GPMProvider', song:Union[GPMSong, EntryOverview]):
        self.cache_dir = Path(cache_dir)
        self.gpm = gpm
        self.entry = song if isinstance(song, EntryOverview) else self.gpm.enclose_entry(song)

        self.title = self.entry.title
        self.uri = self.entry.uri
        self.song_id = uri_to_id(self.uri)
        self.user = uri_to_user(self.uri)
        self.thumbnail = self.entry.thumbnail
        self.filename = str(self.cache_dir/f'{self.gpm.name}-{self.user}-{self.song_id}.mp3')
        self.duration = 0
        self.volume = 0
        
        self.start = asyncio.Event()
        self.end = asyncio.Event()

    async def download(self):
        self.start.set()

        if Path(self.filename).is_file():
            log.info(f'Already downloaded: {self.filename}')
        else:
            try:
                await self.gpm.download(self.user, self.song_id, self.filename)
                log.info(f'Downloaded: {self.filename}')
            except:
                log.error('Failed to download: ', exc_info=True)
        
        self.duration = await get_duration(self.filename)
        self.volume = await get_volume(self.filename)

        self.end.set()

    def is_ready(self):
        return Path(self.filename).exists()


class GPMProvider(Provider):
    name = 'gpm'
    resolve_prefixes = ['gpm']
    can_search = True

    def __init__(self, *, credfile=None):
        self.credfile = credfile or 'config/google.auth' # TODO
        self.cred_dir = Path("config/gpm/")

        self.loop = asyncio.get_event_loop()
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.store = StoreManager()
        self.update_lock = asyncio.Event()
        self.gpm = {}
        self.session = ClientSession()
        self.init_client()

    def init_client(self):
        for cred in self.cred_dir.glob("*.auth"):
            cli = Mobileclient()
            if cli.oauth_login(Mobileclient.FROM_MAC_ADDRESS, str(cred)):
                self.gpm[cred.stem] = cli
                log.info(f"Authorized: {cred.stem}")
            else:
                log.error(f"Failed to authorize: {cred.stem}")

        self.loop.create_task(self.update(force=True))
        # self.update_lock.clear()

    async def resolve(self, uri:str) -> Sequence[EntryOverview]:
        try:
            gpm, track, user, track_id = uri.split(':')
        except:
            log.error(f'Invalid uri: {uri}')
            return []

        if not gpm == 'gpm' or not track == 'track':
            log.error(f'Not a gpm uri: {uri}')
            return []

        await self.update_lock.wait()
        song = None
        try:
            song = await self.store.resolve(user, track_id)
        except:
            log.error(f'DB failed: ', exc_info=True)

        return [self.enclose_entry(song)] if song else []

    async def resolve_playable(self, uri:Union[str, EntryOverview], cache_dir) -> Sequence[GPMEntry]:
        resolved = await self.resolve(uri) if isinstance(uri, str) else [uri]
        return [GPMEntry(cache_dir, self, song) for song in resolved]

    async def search(self, keyword:str) -> Sequence[EntryOverview]:
        await self.update_lock.wait()
        ret = []
        try:
            ret = await self.store.search(keyword)
        except:
            log.error('Failed to search: ', exc_info=True)

        return [self.enclose_entry(entry) for entry in ret[:50]]

    async def update(self, force=False):
        if not force and not self.update_lock.is_set():
            log.error('Update ongoing. skipping...')
            return

        self.update_lock.clear()
        user_songs = {}

        for name, cli in self.gpm.items():
            res = await self.loop.run_in_executor(self.pool, cli.get_all_songs)
            log.info(f'{name}: Retrieved {len(res)} songs')
            if res:
                user_songs[name] = res

        entries = []
        for user, songs in user_songs.items():
            for song in songs:
                album = song.get('albumArtRef')
                album_url = ''
                if album:
                    album_url = album[0].get('url').replace('http://', 'https://', 1)
                entry = GPMSong(user, song.get('id', ''), song.get('title', ''),
                                song.get('artist', ''), song.get('album', ''),
                                album_url)
                entries.append(entry)
        try:
            await self.store.update(entries)
        except:
            log.error('Failed to update gpm database')
        
        self.update_lock.set()

    async def get_mp3(self, user, song_id:str) -> Optional[str]:
        cli = self.gpm.get(user)
        if not cli:
            log.error(f"Client not found for user {user}")
            return

        mp3 = None
        try:
            mp3 = await self.loop.run_in_executor(self.pool, partial(cli.get_stream_url, song_id, quality='med'))
        except:
            log.error('Failed to get audio file: ', exc_info=True)

        return mp3

    async def download(self, user, song_id:str, filename:str):
        mp3 = await self.get_mp3(user, song_id)
        ret = None
        async with self.session.get(mp3) as res:
            if res.status == 200:
                ret = await res.read()

        if not ret:
            raise GPMError()

        await self.loop.run_in_executor(self.pool, partial(save_file, filename, ret))

    def enclose_entry(self, entry:GPMSong) -> EntryOverview:
        title = f'{entry.title} - {entry.artist}'
        uri = get_song_uri(entry)
        art = (entry.albumArtUrl + "=s460-c-e100-rwu-v1") if entry.albumArtUrl else ""
        art_small = (entry.albumArtUrl + "=s158-c-e100-rwu-v1") if entry.albumArtUrl else ""
        return EntryOverview(
            self.name, title, uri,
            art, art_small,
            entry._asdict()
        )
