import asyncio
from asyncio.tasks import ALL_COMPLETED
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
from .utils import GPMError, GPMSong, get_song_uri, id_to_uri, uri_to_id, uri_to_user

log = getLogger(__name__)


class GPMEntry(PlayableEntry):
    def __init__(self, cache_dir, gpm:'GPMProvider', entry:EntryOverview):
        self.cache_dir = Path(cache_dir)
        self.gpm = gpm
        self.entry = entry

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
                self.end.set()
                return
        
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
        self.gpm = {}
        self.subscribed = None
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

        # get subscribed user
        for name, cli in self.gpm.items():
            if cli.is_subscribed:
                log.info(f'Subscribed account: {name}')
                self.subscribed = cli

    async def resolve(self, uri:str) -> Sequence[EntryOverview]:
        try:
            gpm, track, user, track_id = uri.split(':')
        except:
            log.error(f'Invalid uri: {uri}')
            return []

        if not gpm == 'gpm':
            log.error(f'Not a gpm uri: {uri}')
            return []

        ret = None
        try:
            if track == 'track':
                songs = await self.store.resolve(uri)
                if songs:
                    ret = [self.enclose_entry(songs)]
            elif track == 'storeTrack':
                # use general entry table, not gpm_meta
                song = await self.loop.run_in_executor(self.pool, partial(self.subscribed.get_track_info, track_id))
                if song:
                    eo = self.enclose_entry(self.create_store_song(song), store=True)
                    self.loop.create_task(self.store.cache_store(eo))
                    ret = [eo]
            else:
                log.error(f'Not a valid uri: {uri}')
        except:
            log.error(f'resolver failed: ', exc_info=True)

        return ret or []

    async def resolve_playable(self, uri:Union[str, EntryOverview], cache_dir) -> Sequence[GPMEntry]:
        resolved = await self.resolve(uri) if isinstance(uri, str) else [uri]
        return [GPMEntry(cache_dir, self, song) for song in resolved]

    async def search(self, keyword:str) -> Sequence[EntryOverview]:
        ret = []
        todo = [
            self.search_local(keyword),
            self.search_subscription(keyword)
        ]

        try:
            results = await asyncio.wait_for(asyncio.gather(*todo, return_exceptions=True), timeout=5)
        except:
            log.error(f"Task timed out!: ", exc_info=True)
            return ret

        # extract results
        for item in results:
            if isinstance(item, Exception):
                log.error(f"Got error while extracting search results: {item}")
            else:
                ret += item
        
        return ret

    async def search_local(self, keyword:str) -> Sequence[EntryOverview]:
        ret = []
        try:
            ret = await self.store.search(keyword)
        except:
            log.error('Failed to search: ', exc_info=True)

        return [self.enclose_entry(entry) for entry in ret]

    async def search_subscription(self, query:str) -> Sequence[EntryOverview]:
        if not self.subscribed:
            log.error('No subscribed account found.')
            return []
        
        ret = []
        result = await self.loop.run_in_executor(self.pool, partial(self.subscribed.search, query))
        for item in result['song_hits']:
            track = item['track']
            if not track['trackAvailableForSubscription']:
                log.info(f"Track {track['title']} is not available for subscription.")
                continue

            ret.append(self.create_store_song(track))

        return [self.enclose_entry(entry, store=True) for entry in ret]

    async def update(self, user=None):
        to_update = self.gpm
        if user:
            if user in self.gpm:
                to_update = { user: self.gpm[user] }
            else:
                log.error(f"User not found: {user}")
                return

        user_songs = {}

        for name, cli in to_update.items():
            res = await self.loop.run_in_executor(self.pool, cli.get_all_songs)
            log.info(f'{name}: Retrieved {len(res)} songs')
            if res:
                user_songs[name] = res

        entries = []
        for _, songs in user_songs.items():
            for song in songs:
                album = song.get('albumArtRef')
                album_url = ''
                if album:
                    album_url = album[0].get('url').replace('http://', 'https://', 1)
                # entry = GPMSong(user, song.get('id', ''), song.get('title', ''),
                #                 song.get('artist', ''), song.get('album', ''),
                #                 album_url)
                entries.append({
                    "uri": f"gpm:track:{user}:{song.get('id')}",
                    "gpmUser": user,
                    "id": song.get("id"),
                    "title": song.get("title"),
                    "artist": song.get("artist", ""),
                    "album": song.get("album", ""),
                    "thumbnail": album_url
                })
        try:
            await self.store.update(entries, user)
        except:
            log.error('Failed to update gpm database')
        
    async def get_mp3(self, user, song_id:str) -> Optional[str]:
        cli = self.subscribed if user == 'store' else self.gpm.get(user)
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

    def enclose_entry(self, entry:GPMSong, store=False) -> EntryOverview:
        title = f'{entry.title} - {entry.artist}'
        uri = get_song_uri(entry, store)
        art_small = (entry.albumArtUrl + "=s158-c-e100-rwu-v1") if entry.albumArtUrl else ""
        eo = EntryOverview(
            self.name, title, uri,
            entry.albumArtUrl.replace("http://", "https://"), art_small.replace("http://", "https://"),
            entry._asdict()
        )
        # eo.is_liked = entry.is_liked
        return eo

    def create_store_song(self, track:dict) -> GPMSong:
        album_art = track['albumArtRef'][0]['url'] if track['albumArtRef'] else ''
        return GPMSong(
            'store', track['storeId'],
            track['title'], track['artist'], track['album'],
            album_art.replace("http://", "https://"), False
        )
