import asyncio
from logging import getLogger
from aria.models import PlayableEntry, EntryOverview, PlayerState
from typing import Sequence, Union

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
            async with self.lock:
                try:
                    ret = self.queue.popleft()
                except:
                    pass
            
            if not ret:
                break
            if not ret.ready.is_set():
                try:
                    await asyncio.wait_for(ret.ready.wait(), 10) # FIXME
                    break
                except:
                    continue

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
        if not entry.process:
            try:
                await asyncio.wait_for(entry.download(), 30)
            except:
                log.error(f'Failed to download entry {entry.uri}: ', exc_info=True)
            finally:
                if not entry.ready.is_set():
                    self.remove_entry(entry)
        
    @property
    def list(self) -> Sequence[EntryOverview]:
        return [item.entry for item in self.queue]


class Player():
    def __init__(self, manager, stream):
        self.prov = manager
        self.stream = stream
        self.loop = asyncio.get_event_loop()

        self.lock = asyncio.Lock()
        self.state = PlayerState.PAUSED
        self.queue = PlayerQueue(self)
        self.current = None

    async def play(self):
        if self.state == PlayerState.STOPPED:
            async with self.lock:
                to_play = await self.queue.get_next()
                if not to_play:
                    return

                self.stream.


    async def pause(self):
        pass

    async def resume(self):
        pass

    async def add_entry(self, uri):
        entry = await self.prov.resolve_playable(uri, self)
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
        """
        Should be passed to StreamPlayer
        """
        pass

    def on_download_failed(self, entry:PlayableEntry):
        pass
