import asyncio
from collections import deque
from logging import getLogger
from random import shuffle
from typing import Sequence, Union

from aria.models import EntryOverview, PlayableEntry, PlayerState
from aria.stream import StreamPlayer

log = getLogger(__name__)


class PlayerQueue():
    def __init__(self, player):
        self.player = player
        self.on_queue_change = self.player.view.on_queue_change
        self.on_queue_empty = self.player.view.on_queue_empty

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
                    self.on_queue_empty()
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

        self.on_queue_change()
        return ret

    async def add_entry(self, entries:Union[Sequence[PlayableEntry], PlayableEntry], head=False, shuffle=False):
        to_add = entries if isinstance(entries, list) else [entries]
        async with self.lock:
            if head:
                self.queue.extendleft(to_add[::-1])
            else:
                self.queue.extend(to_add)

        if shuffle:
            await self.shuffle()

        self.loop.create_task(self.prepare(self.queue[0]))
        self.player.on_entry_added()
        self.on_queue_change()

    async def remove_entry(self, entry):
        async with self.lock:
            try:
                self.queue.remove(entry)
                self.loop.create_task(self.prepare(self.queue[0]))
                self.on_queue_change()
            except:
                pass

    async def remove(self, uri, index):
        async with self.lock:
            try:
                to_delete = self.queue[index]
            except:
                log.error(f'Entry not found for index {index}')
                return

            if to_delete.uri != uri:
                log.error('Uri mismatch!')
                return

            self.loop.create_task(self.remove_entry(to_delete))

    async def seek(self, uri, index):
        async with self.lock:
            if not self.queue[index].uri == uri:
                log.error('Uri mismatch.')
                return
            
            # do we need to check queue length?
            try:
                for _ in range(index):
                    self.queue.popleft()
            except:
                log.error('Queue length not enough. Fuck client.')
        
        # dont call on_queue_change since next get_entry does it well

    async def assign(self, uris):
        async with self.lock:
            if len(uris) != len(self.queue):
                log.error('Queue length mismatch. Cannot assign.')
                return
            
            indexes = []

            current_uris = [x.uri for x in self.queue]
            for index, (current, new) in enumerate(zip(current_uris, uris)):
                if not current == new:
                    indexes.append(index)

            if len(indexes) == 2:
                self.queue[indexes[0]], self.queue[indexes[1]] = self.queue[indexes[1]], self.queue[indexes[0]]
                self.on_queue_change()
            else:
                log.error('Invalid request...?')

    async def clear(self):
        async with self.lock:
            self.queue.clear()

        self.on_queue_change()

    async def prepare(self, entry):
        if not entry.start.is_set():
            try:
                await asyncio.wait_for(entry.download(), 30)
            except:
                log.error(f'Failed to download entry {entry.uri}: ', exc_info=True)
            finally:
                if not entry.is_ready():
                    log.info('Entry not ready. Delete.')
                    await self.remove_entry(entry)

    async def shuffle(self):
        # random access to deque is slow:
        # https://bugs.python.org/issue4123
        # so we convert queue to list and shuffle
        # then revert list back to deque
        async with self.lock:
            pq = list(self.queue)
            shuffle(pq)
            self.queue = deque(pq)
            if len(self.queue):
                self.loop.create_task(self.prepare(self.queue[0]))

        self.on_queue_change()
        
    @property
    def list(self) -> Sequence[EntryOverview]:
        return [item.entry for item in self.queue]


class Player():
    def __init__(self, view, manager):
        self.view = view
        self.prov = manager
        self.stream = StreamPlayer(self)
        self.loop = asyncio.get_event_loop()

        self.lock = asyncio.Lock()
        self.state = PlayerState.STOPPED
        self.queue = PlayerQueue(self)
        self.current = None

    async def play(self):
        async with self.lock:
            if self.state == PlayerState.STOPPED:
                self.current = await self.queue.get_next()
                if not self.current:
                    return

                self.change_state('playing')
                self.stream.play(self.current.filename)

    async def pause(self):
        async with self.lock:
            if self.state == PlayerState.PLAYING:
                self.change_state('paused')
                self.stream.pause()

    async def resume(self):
        async with self.lock:
            if self.state == PlayerState.PAUSED:
                self.change_state('playing')
                self.stream.resume()

    async def skip(self):
        async with self.lock:
            self.change_state('stopped')
            self.stream.stop()
            self.loop.create_task(self.play())

    # TODO: do resolve in playqueue
    async def add_entry(self, uri, head):
        entry = await self.prov.resolve_playable(uri)
        if entry:
            await self.queue.add_entry(entry, head)

    async def repeat(self, uri, count):
        async with self.lock:
            if not self.current.uri == uri:
                log.error('URI mismatch.')
                return

            self.loop.create_task(self.queue.add_entry([self.current] * count, head=True))

    @property
    def list(self):
        return self.queue.list

    def change_state(self, state_to:str):
        # MUST BE CALLED WITH LOCK ACQUIRED!!!
        self.state = PlayerState[state_to.upper()]
        self.view.on_player_state_change()        

    def enclose_state(self):
        return {
            'state': self.state.name.lower(),
            'entry': {
                **self.current.entry.as_dict(),
                'is_liked': self.view.playlist.is_liked(self.current.entry.uri)
            } if not self.state == PlayerState.STOPPED else None
        }

    # Callbacks

    def on_entry_added(self):
        self.loop.create_task(self.do_on_entry_added())

    async def do_on_entry_added(self):
        async with self.lock:
            if self.state == PlayerState.STOPPED:
                self.loop.create_task(self.play()) # don't await or you got DEADLOCK

    def on_play_finished(self):
        self.loop.create_task(self.do_on_play_finished())

    async def do_on_play_finished(self):
        async with self.lock:
            log.debug('Play finished!')
            self.change_state('stopped')            
            self.loop.create_task(self.play())
