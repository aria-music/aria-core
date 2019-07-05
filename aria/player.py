import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from logging import getLogger
from typing import Sequence, Union

from aria.models import EntryOverview, PlayableEntry, PlayerState
from aria.stream import StreamPlayer

log = getLogger(__name__)


class PlayerQueue():
    def __init__(self, player):
        self.player = player

        self.loop = asyncio.get_event_loop()
        self.queue = deque()
        self.lock = asyncio.Lock()
        
    async def get_next(self):
        ret = None
        while True:
            ret = None
            log.debug('Looking for next entry...')
            async with self.lock:
                try:
                    ret = self.queue.popleft()
                except:
                    log.error('No entry.')
                    break
            
            if not ret.end.is_set():
                log.info('Entry is not ready. Waiting...')
                try:
                    await asyncio.wait_for(ret.end.wait(), 10)
                except:
                    log.error('Download timed out. Skip.', exc_info=True)
                    continue
            
            if ret.is_ready():
                break
        
        try:
            self.loop.create_task(self.prepare(self.queue[0]))
        except:
            pass

        return ret

    def add_entry(self, entries:Union[Sequence[PlayableEntry], PlayableEntry], head=False):
        to_add = entries if isinstance(entries, list) else [entries]
        if head:
            self.queue.extendleft(to_add[::-1])
        else:
            self.queue.extend(to_add)

        self.loop.create_task(self.prepare(self.queue[0]))
        self.player.on_entry_added()

    def remove_entry(self, entry):
        try:
            self.queue.remove(entry)
            self.loop.create_task(self.prepare(self.queue[0]))
        except:
            pass

    async def prepare(self, entry):
        if not entry.start.is_set():
            try:
                await asyncio.wait_for(entry.download(), 30)
            except:
                log.error(f'Failed to download entry {entry.uri}: ', exc_info=True)
            finally:
                if not entry.is_ready():
                    log.info('Entry not ready. Delete.')
                    self.remove_entry(entry)
        
    @property
    def list(self) -> Sequence[EntryOverview]:
        return [item.entry for item in self.queue]


class Player():
    def __init__(self, manager):
        self.prov = manager
        self.stream = StreamPlayer(self)
        self.loop = asyncio.get_event_loop()

        self.pool = ThreadPoolExecutor(max_workers=4)
        self.lock = asyncio.Lock()
        self.state = PlayerState.STOPPED
        self.queue = PlayerQueue(self)
        self.current = None

    async def play(self):
        async with self.lock:
            self.current = await self.queue.get_next()
            if not self.current:
                return

            self.state = PlayerState.PLAYING
            await self.loop.run_in_executor(self.pool, partial(self.stream.play, self.current.filename))

    async def pause(self):
        async with self.lock:
            if self.state == PlayerState.PLAYING:
                self.state = PlayerState.PAUSED
                await self.loop.run_in_executor(self.pool, self.stream.pause)

    async def resume(self):
        async with self.lock:
            if self.state == PlayerState.PAUSED:
                self.state = PlayerState.PLAYING
                await self.loop.run_in_executor(self.pool, self.stream.resume)

    async def skip(self):
        async with self.lock:
            self.state = PlayerState.STOPPED
            # await self.loop.run_in_executor(self.pool, self.stream.stop)
            self.loop.create_task(self.play())

    # TODO: do resolve in playqueue
    async def add_entry(self, uri):
        entry = await self.prov.resolve_playable(uri)
        if entry:
            self.queue.add_entry(entry)

    @property
    def list(self):
        return self.queue.list

    # Callbacks

    def on_entry_added(self):
        if self.state == PlayerState.STOPPED:
            self.loop.create_task(self.play())

    def on_play_finished(self):
        self.loop.create_task(self.do_on_play_finished())

    async def do_on_play_finished(self):
        async with self.lock:
            self.state = PlayerState.STOPPED
            log.debug('Play finished!')
            self.loop.create_task(self.play())

    def on_download_failed(self, entry:PlayableEntry):
        pass
