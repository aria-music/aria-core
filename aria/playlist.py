import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from logging import getLogger
from pathlib import Path
from random import choice
from typing import Sequence, Union

from aria.models import EntryOverview, PlayableEntry

log = getLogger(__name__)


class Playlist():
    def __init__(self, view, name, file:Union[str, Path], provider, pool=None, loop=None):
        self.view = view
        self.name = name
        self.file = file
        self.prov = provider
        self.pool = pool or ThreadPoolExecutor(max_workers=8)
        self.loop = loop or asyncio.get_event_loop()
        
        self.lock = asyncio.Lock(loop=self.loop)
        self.list = {}

        #self.loop.create_task(self.load_file())
        self.do_load_file()

    @classmethod
    def create(cls, view, name, filename, provider, pool, loop):
        file = Path(filename)
        file.touch()

        return cls(view, name, filename, provider, pool, loop)

    def add(self, entry:Union[Sequence[EntryOverview], EntryOverview]):
        entries = entry if isinstance(entry, list) else [entry]

        for item in entries:
            if isinstance(item, EntryOverview):
                self.list[item.uri.strip()] = item
            else:
                stripped = item.uri.stripped()
                if stripped and stripped not in self.list.keys():
                    self.list[stripped] = None
        
        self.loop.create_task(self.save_file())
        self.view.on_playlists_change()
        self.view.on_playlist_entry_change(self.name)
    
    def remove(self, entry:Union[str, list]):
        entries = entry if isinstance(entry, list) else [entry]

        for item in entries:
            stripped = item.strip()
            if stripped and stripped in self.list.keys():
                self.list.pop(stripped)
        
        self.loop.create_task(self.save_file())
        self.view.on_playlists_change()
        self.view.on_playlist_entry_change(self.name)

    async def random(self):
        try:
            key, val = choice(list(self.list.items()))
        except:
            log.error('Playlist is empty!')
            return

        if not val:
            val = await self.fill_resolve(key)
        return val

    async def fill_resolve(self, key):
        if self.list[key]:
            return
        
        ret = await self.prov.resolve(key)
        if not len(ret) == 1:
            log.error('Something went wrong...?')
            return

        self.list[key] = ret[0]
        return self.list[key]

    async def get_thumbnails(self):
        need_resolve = [self.fill_resolve(k) for k, v in list(self.list.items())[:4] if not v]
        # log.debug(f'{self.name}: {len(need_resolve)} entries are incomplete')
        if need_resolve:
            await asyncio.wait(need_resolve, return_when=asyncio.ALL_COMPLETED)

        return [v.thumbnail for k, v in list(self.list.items())[:4] if v]

    async def get_entries(self) -> Sequence[EntryOverview]:
        unresolved = [self.fill_resolve(k) for k, v in self.list.items() if not v]
        if unresolved:
            await asyncio.wait(unresolved, return_when=asyncio.ALL_COMPLETED)
        return [item for item in self.list.values() if item]

    async def get_playable_entries(self) -> Sequence[PlayableEntry]:
        return await self.view.manager.resolve_playable(await self.get_entries())

    async def load_file(self):
        async with self.lock:
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
        async with self.lock:
            await self.loop.run_in_executor(self.pool, self.do_save_file)

    def do_save_file(self):
        file = Path(self.file) if isinstance(self.file, str) else Path(self.file)
        try:
            with file.open('w') as f:
                f.write('\n'.join(self.list.keys()))
        except:
            log.error(f'Failed to save playlist to file {file}: ', exc_info=True)

class PlaylistManager():
    def __init__(self, view, config, provider_manager):
        self.view = view
        self.prov = provider_manager
        self.playlists_dir = config.playlists_dir
        self.loop = asyncio.get_event_loop()
        self.pool = ThreadPoolExecutor(max_workers=4)

        self.lists = {}
        self.likes = None # special playlist

        # self.loop.create_task(self.load_playlists())
        self.do_load_playlists()
        self.init_likes()

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
                    self.lists[file.stem] = Playlist(self.view, file.stem, file, self.prov, self.pool, self.loop)
                    log.debug(f'Loaded {file.stem}: {self.lists[file.stem]}')
                except:
                    log.error(f'Failed to initialize playlist {file.stem}: ', exc_info=True)
        except:
            log.error('Failed to initialize playlists: ', exc_info=True)

    def init_likes(self):
        if 'Likes' in self.lists:
            log.info('Found likes list.')
            self.likes = self.lists['Likes']
            log.debug(self.likes)
        else:
            log.info('Likes list not found. Creating...')
            self.likes = self.do_create('Likes')
            self.lists['Likes'] = self.likes

        self.loop.create_task(self.likes.get_entries())
        
    @property
    def list(self):
        return list(self.lists.keys())

    async def enclose_playlists(self):
        let_enclose = [pl.get_thumbnails() for pl in self.lists.values()]
        await asyncio.wait(let_enclose, return_when=asyncio.ALL_COMPLETED)
        ret = [{
            'name': self.likes.name,
            'length': len(self.likes.list),
            'thumbnails': await self.likes.get_thumbnails()
        }]

        for name, pl in self.lists.items():
            if not pl == self.likes:
                ret.append({
                    'name': name,
                    'length': len(pl.list),
                    'thumbnails': await pl.get_thumbnails()
                })

        return ret

    def get_playlist(self, name:str):
        log.debug(list(self.lists.keys()))
        ret = None
        try:
            ret = self.lists[name]
        except:
            log.error(f'list not found for {name}')
        
        return ret

    def is_liked(self, uri):
        return uri.split(':')[-1].strip('./') in [item.split(':')[-1].strip('./') for item in self.likes.list]

    def like(self, uri):
        self.likes.add(uri)

    def dislike(self, uri):
        self.likes.remove(uri)

    async def create(self, name:str):
        if name in self.lists:
            log.error(f'Already exists: {name}')
        else:
            log.info(f'Creating list {name}')
            self.lists[name] = await self.loop.run_in_executor(self.pool, partial(self.do_create, name))
            self.view.on_playlists_change()

    def do_create(self, name):
        return Playlist.create(self.view, name, Path(self.playlists_dir)/f'{name}.aria', self.prov, self.pool, self.loop)

    def delete(self, name:str):
        if name == 'Likes':
            log.error('You cannot delete Likes list!!!')
            return

        if name in self.lists:
            self.lists.pop(name)
            log.info(f'Deleted playlist {name}')
            self.view.on_playlists_change()
