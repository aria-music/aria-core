import asyncio
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from logging import getLogger
from pathlib import Path
from typing import Sequence

from youtube_dl import YoutubeDL

from aria.models import EntryOverview, PlayableEntry, Provider
from aria.utils import get_duration

log = getLogger(__name__)

ytdl_params = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'quiet': True,
    'logtostderr': False
}


class YoutubeDLEntry(PlayableEntry):
    def __init__(self, cache_dir, ytdl:'YTDLProvider', song:EntryOverview, filename=None):
        self.cache_dir = Path(cache_dir)
        self.ytdl = ytdl
        self.entry = song

        self.title = self.entry.title
        self.uri = self.entry.uri
        self.thumbnail = self.entry.thumbnail
        self.expected_filename = (self.cache_dir/filename) if filename else None
        self.filename = None
        self.duration = None
    
        self.start = asyncio.Event()
        self.end = asyncio.Event()

    async def download(self):
        self.start.set()
        log.debug(f'looking for caches: {str(self.expected_filename)}')
        if self.expected_filename and self.expected_filename.exists():
                self.filename = str(self.expected_filename)
                log.info(f'Use cached: {self.expected_filename}')
        else:
            try:
                filename = await self.ytdl.download(self.uri)
                dest = Path(self.cache_dir)/filename
                Path(filename).rename(dest)
                self.filename = str(dest)
                log.info(f'Downloaded: {self.filename}')
            except:
                log.error('Moving file failed: ', exc_info=True)

        self.duration = await get_duration(self.filename)
        
        self.end.set()

    def is_ready(self):
        if self.filename:
            return Path(self.filename).exists()
        else:
            return False
            

class YTDLProvider(Provider):
    name = 'ytdl'
    resolve_prefixes = ['http', 'https']

    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.ytdl = YoutubeDL(ytdl_params)

    async def resolve(self, uri) -> Sequence[EntryOverview]:
        try:
            res = await self.loop.run_in_executor(self.pool, partial(self.ytdl.extract_info, uri, download=False))
            log.debug(res.get('extractor'))
        except:
            log.error('Failed to extract uri: ', exc_info=True)
            return []
        
        ret = []
        if 'entries' in res:
            for entry in res['entries']:
                if 'is_live' in entry and entry['is_live'] == True:
                    continue

                ret.append(EntryOverview(res['extractor'].split(':')[0],
                                         entry.get('title') or '',
                                         entry.get('webpage_url') or '',
                                         entry.get('thumbnail') or '',
                                         entry))
        else:
            if 'is_live' in res and res['is_live'] == True:
                pass
            else:
                ret.append(EntryOverview(res['extractor'].split(':')[0],
                                        res.get('title') or '',
                                        res.get('webpage_url') or '',
                                        res.get('thumbnail') or '',
                                        res))

        return ret

    async def resolve_playable(self, uri, cache_dir) -> Sequence[YoutubeDLEntry]:
        resolved = await self.resolve(uri) if isinstance(uri, str) else [uri]
        ret = []
        for song in resolved:
            try:
                filename = await self.loop.run_in_executor(self.pool, partial(self.ytdl.prepare_filename, song.entry))
                log.debug(f'Expected filename: {filename}')
                ret.append(YoutubeDLEntry(cache_dir, self, song, filename))
            except:
                log.error('Failed to generate filename:', exc_info=True)
        return ret

    async def download(self, uri):
        filename = None
        try:
            res = await self.loop.run_in_executor(self.pool, partial(self.ytdl.extract_info, uri, download=True))
            filename = await self.loop.run_in_executor(self.pool, partial(self.ytdl.prepare_filename, res))
        except:
            log.error('Download failed. YoutubeDL sucks: ', exc_info=True)
        
        return filename

    async def search(self, query):
        # resolve-only provider
        return
