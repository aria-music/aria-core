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
    def __init__(self, cache_dir, ytdl:'YTDLProvider', song:EntryOverview):
        self.cache_dir = Path(cache_dir)
        self.ytdl = ytdl
        self.entry = song

        self.title = self.entry.title
        self.uri = self.entry.uri
        self.thumbnail = self.entry.thumbnail
        self.filename = None
    
        self.process = False
        self.ready = asyncio.Event()

    async def download(self):
        self.process = True
        self.filename = await self.ytdl.download(self.uri)
        if self.filename:
            try:
                dest = Path(self.cache_dir)/self.filename
                Path(self.filename).rename(dest)
                self.filename = str(dest)
                self.ready.set()
            except:
                log.error('Moving file failed:\n', exc_info=True)

        log.info(f'Downloaded: {self.filename}' if self.filename else 'Failed to download')
        # if not self.ready.is_set():
        #     self.player.cb_download_failed(self)


class YTDLProvider(Provider):
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
            log.error('Failed to extract uri:\n', exc_info=True)
            return []
        
        ret = []
        if 'entries' in res:
            for entry in res['entries']:
                if 'is_live' in entry and entry['is_live'] == True:
                    continue

                ret.append(EntryOverview(res['extractor'].split(':')[0],
                                         entry.get('title') or '',
                                         entry.get('webpage_url') or '',
                                         entry.get('thumbnail') or ''))
        else:
            if 'is_live' in res and res['is_live'] == True:
                pass
            else:
                ret.append(EntryOverview(res['extractor'].split(':')[0],
                                        res.get('title') or '',
                                        res.get('webpage_url') or '',
                                        res.get('thumbnail') or ''))

        return ret

    async def resolve_playable(self, uri, cache_dir) -> Sequence[YoutubeDLEntry]:
        resolved = await self.resolve(uri)
        return [YoutubeDLEntry(cache_dir, self, song) for song in resolved]

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
