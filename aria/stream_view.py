import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from logging import getLogger
from threading import Thread
from time import sleep, time

from aiohttp import WSMsgType, web

log = getLogger(__name__)


class StreamView():
    def __init__(self, config, player_view):
        self.config = config
        self.player_view = player_view
        self.stream = self.player_view.player.stream

        self.loop = asyncio.get_event_loop()
        self.pool = ThreadPoolExecutor(max_workers=2)

        self.connections = {}
        # self.refresh_thread = Thread(target=self.refresh_connections)
        # self.refresh_thread.start()

        self.stream_thread = Thread(target=self.streaming)
        self.stream_thread.start()

    # def refresh_connections(self):
    #     # CALLED FROM OTHER THREAD!
    #     # don't need lock since sending to closed ws and raising exception is no matter
    #     while True:
    #         self.connections = [ws for ws in self.connections if not ws.closed]
    #         # log.debug(f'Stream holding {len(self.connections)} connections')
    #         sleep(1) # roughly

    async def get_ws(self, request):
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        log.info('New connection on stream')

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                if msg.data in self.player_view.connections:
                    log.info('stream connection approved')
                    self.connections[msg.data] = ws
                    log.debug(f'Current stream: {len(self.connections)} connections')
                else:
                    log.info('stream connection refused')
                    await ws.close()

        return ws

    async def broadcast(self, packet):
        for key, ws in self.connections.items():
            self.loop.create_task(self.send_bytes(key, ws, packet))

    async def send_bytes(self, key, ws, packet):
        if ws.exception() != None or ws.closed:
            log.info('Deleting closed connection...')
            self.delete_connection(key)
        else:
            try:
                await ws.send_bytes(packet)
            except:
                log.error('Failed to send. Deleting connection...')
                self.delete_connection(key)

    def delete_connection(self, key):
        self.loop.run_in_executor(self.pool, partial(self.do_delete_connection, key))

    def do_delete_connection(self, key):
        try:
            self.connections.pop(key)
        except:
            log.error(f'Connection not found for key {key}')

        log.debug(f'Current stream: {len(self.connections)} connections')

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
