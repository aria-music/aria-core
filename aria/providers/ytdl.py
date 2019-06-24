import asyncio
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from logging import getLogger
from pathlib import Path
from typing import Sequence

from youtube_dl import YoutubeDL

from aria.models import EntryOverview, PlayableEntry, Provider

log = getLogger(__name__)

ytdl_params = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'quiet': True,
}


class YoutubeDLEntry(PlayableEntry):
    def __init__(self, playlist, ytdl:'YTDLProvider', song:EntryOverview):
        self.playlist = playlist
        self.ytdl = ytdl
        self.entry = song

        self.title = self.entry.title
        self.uri = self.entry.uri
        self.thumbnail = self.entry.thumbnail
        self.filename = None
    
        self.ready = asyncio.Event()

    async def download(self):
        self.filename = await self.ytdl.download(self.uri)
        if self.filename:
            try:
                Path(self.filename).rename(Path(self.playlist.cache_dir)/self.filename)
                self.ready.set()
            except:
                log.error('Moving file failed:\n', exc_info=True)

        if not self.ready.is_set():
            self.playlist.cb_download_failed()


class YTDLProvider(Provider):
    resolve_prefixes = ['http', 'https']

    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.ytdl = YoutubeDL(ytdl_params)

    async def resolve(self, uri) -> Sequence[EntryOverview]:
        try:
            res = await self.loop.run_in_executor(self.loop, partial(self.ytdl.extract_info, uri, download=False))
        except:
            log.error('Failed to extract uri:\n', exc_info=True)
        
        ret = []
        if 'entries' in res:
            for entry in res['entries']:
                ret.append(EntryOverview(res['extractor'].split(':')[0],
                                         entry.get('title'),
                                         entry.get('webpage_url'),
                                         entry.get('thumbnail')))
        else:
            ret.append(EntryOverview(res['extractor'].split(':')[0],
                                     res.get('title'),
                                     res.get('webpage_url'),
                                     res.get('thumbnail')))

        return ret

    async def download(self, uri):
        filename = None
        try:
            res = await self.loop.run_in_executor(self.pool, partial(self.ytdl.extract_info, uri, download=True))
            filename = await self.loop.run_in_executor(self.pool, partial(self.ytdl.prepare_filename, res))
        except:
            log.error('Download failed. YoutubeDL sucks:\n', exc_info=True)
        
        return filename

    async def search(self, query):
        # resolve-only provider
        return
