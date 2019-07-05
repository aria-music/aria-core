from aiohttp import web, WSMsgType
import asyncio
from time import time, sleep
from concurrent.futures import ThreadPoolExecutor
from logging import getLogger
from threading import Thread

log = getLogger(__name__)


class StreamView():
    def __init__(self, config, player_view):
        self.config = config
        self.player_view = player_view
        self.stream = self.player_view.player.stream

        self.loop = asyncio.get_event_loop()
        self.pool = ThreadPoolExecutor(max_workers=2)

        self.connections = []
        self.refresh_thread = Thread(target=self.refresh_connections)
        self.refresh_thread.start()

        self.stream_thread = Thread(target=self.streaming)
        self.stream_thread.start()

    def refresh_connections(self):
        # CALLED FROM OTHER THREAD!
        # don't need lock since sending to closed ws and raising exception is no matter
        while True:
            self.connections = [ws for ws in self.connections if not ws.closed]
            # log.debug(f'Stream holding {len(self.connections)} connections')
            sleep(1) # roughly

    async def get_ws(self, request):
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        log.info('New connection on stream')

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                if msg.data in self.player_view.connections:
                    log.info('stream connection approved')
                    self.connections.append(ws)
                else:
                    log.info('stream connection refused')
                    await ws.close()

        return ws

    async def broadcast(self, packet):
        for ws in self.connections:
            self.loop.create_task(ws.send_bytes(packet))

    def streaming(self):
        # CALLED FROM OTHER THREAD!
        looptime = time()
        while True:
            # log.debug('running')
            looptime += 0.02

            pack = self.stream.read()
            if pack:
                asyncio.run_coroutine_threadsafe(self.broadcast(pack), self.loop)

            sleep(max(0, looptime-time()))
