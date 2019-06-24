import asyncio
from concurrent.futures import ThreadPoolExecutor
from logging import getLogger
from pathlib import Path
from random import choice
from typing import Union

log = getLogger(__name__)


class Playlist():
    def __init__(self, filename:str, pool=None):
        self.filename = filename
        self.pool = pool or ThreadPoolExecutor(max_workers=4)

        self.loop = asyncio.get_event_loop()
        self.list = []

        self.loop.create_task(self.load_file())

    def add(self, entry:Union[str, list]):
        entries = entry if isinstance(entry, list) else [entry]

        for item in entries:
            stripped = item.strip()
            if item and item not in self.list:
                self.list.append(item)
        
        self.loop.create_task(self.save_file())
    
    def remove(self, entry:Union[str, list]):
        entries = entry if isinstance(entry, list) else [entry]

        for item in entries:
            stripped = item.strip()
            if item and item in self.list:
                self.list.remove(item)
        
        self.loop.create_task(self.save_file())

    def random(self):
        ret = None
        try:
            ret = choice(self.list)
        except:
            log.error('Playlist is empty!')

        return ret

    async def load_file(self):
        await self.loop.run_in_executor(self.pool, self.do_load_file)

    def do_load_file(self):
        try:
            with Path(self.filename).open('r') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        self.list.append(stripped)
        except:
            log.error(f'Failed to load playlist from file {self.filename}: ', exc_info=True)

    async def save_file(self):
        await self.loop.run_in_executor(self.pool, self.do_save_file)

    def do_save_file(self):
        try:
            with Path(self.filename).open('w') as f:
                for line in self.list:
                    f.write(line)
        except:
            log.error(f'Failed to save playlist to file {self.filename}: ', exc_info=True)
