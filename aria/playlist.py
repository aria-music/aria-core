import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from logging import getLogger
from pathlib import Path
from random import choice
from typing import Optional, Sequence, Union

from aria.models import EntryOverview

log = getLogger(__name__)


class Playlist():
    def __init__(self, file:Union[str, Path], provider, pool=None, loop=None):
        self.file = file
        self.prov = provider
        self.pool = pool or ThreadPoolExecutor(max_workers=4)

        self.loop = loop or asyncio.get_event_loop()
        self.list = {}

        #self.loop.create_task(self.load_file())
        self.do_load_file()

    @classmethod
    def create(cls, filename, provider, pool, loop):
        file = Path(filename)
        file.touch()

        return cls(filename, provider, pool, loop)

    def add(self, entry:Union[str, list]):
        entries = entry if isinstance(entry, list) else [entry]

        for item in entries:
            stripped = item.strip()
            if stripped and stripped not in self.list.keys():
                self.list[stripped] = None
        
        self.loop.create_task(self.save_file())
    
    def remove(self, entry:Union[str, list]):
        entries = entry if isinstance(entry, list) else [entry]

        for item in entries:
            stripped = item.strip()
            if stripped and stripped in self.list.keys():
                self.list.pop(stripped)
        
        self.loop.create_task(self.save_file())

    def random(self) -> Optional[str]:
        ret = None
        try:
            ret = choice(list(self.list.values()))
        except:
            log.error('Playlist is empty!')

        return ret

    async def fill_resolve(self, key):
        ret = await self.prov.resolve(key)
        if not len(ret) == 1:
            log.error('Something went wrong...?')
            return

        self.list[key] = ret[0]

    async def get_entries(self) -> Sequence[EntryOverview]:
        unresolved = [self.fill_resolve(k) for k, v in self.list.items() if not v]
        if unresolved:
            await asyncio.wait(unresolved, return_when=asyncio.ALL_COMPLETED)
        return [item for item in self.list.values() if item]

    async def load_file(self):
        await self.loop.run_in_executor(self.pool, self.do_load_file)

    def do_load_file(self):
        file = Path(self.file) if isinstance(self.file, str) else Path(self.file)
        try:
            with file.open('r') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        self.list[stripped] = None
        except:
            log.error(f'Failed to load playlist from file {file}: ', exc_info=True)

    async def save_file(self):
        await self.loop.run_in_executor(self.pool, self.do_save_file)

    def do_save_file(self):
        file = Path(self.file) if isinstance(self.file, str) else Path(self.file)
        try:
            with file.open('w') as f:
                for line in self.list.keys():
                    f.write(line)
        except:
            log.error(f'Failed to save playlist to file {file}: ', exc_info=True)

class PlaylistManager():
    def __init__(self, config, provider_manager):
        self.prov = provider_manager
        self.playlists_dir = config.playlists_dir
        self.loop = asyncio.get_event_loop()
        self.pool = ThreadPoolExecutor(max_workers=4)

        self.lists = {}

        # self.loop.create_task(self.load_playlists())
        self.do_load_playlists()

    async def load_playlists(self):
        await self.loop.run_in_executor(self.pool, self.do_load_playlists)

    def do_load_playlists(self):
        pl_dir = Path(self.playlists_dir)
        log.debug(f'loading {pl_dir}')
        try:
            pl_dir.mkdir(exist_ok=True)
            for file in pl_dir.glob('*.aria'):
                log.info(f'Loading playlist {file}')
                try:
                    self.lists[file.stem] = Playlist(file, self.prov, self.pool, self.loop)
                except:
                    log.error(f'Failed to initialize playlist {file.stem}: ', exc_info=True)
        except:
            log.error('Failed to initialize playlists: ', exc_info=True)
        
    @property
    def list(self):
        return list(self.lists.keys())

    def get_playlist(self, name:str):
        return self.lists.get(name)

    async def create(self, name:str):
        if not name in self.lists.keys():
            self.lists[name] = await self.loop.run_in_executor(
                self.pool,
                partial(Playlist.create, Path(self.playlists_dir)/f'{name}.aria', self.prov, self.pool, self.loop)
            )
