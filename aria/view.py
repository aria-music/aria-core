import asyncio
from string import ascii_letters, digits
import random
from aiohttp import web, WSMsgType
from logging import getLogger

CHARACTERS = ascii_letters + digits
KEY_LENGTH = 40

log = getLogger(__name__)


class PlayerView():
    def __init__(self, config):
        self.config = config
        self.loop = asyncio.get_event_loop()

        self.connections = {}

    async def get_ws(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        log.debug(f"Connected to {request.remote}")

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    self.loop.create_task(self.handle_message(msg.json()))
                except:
                    log.error(f'Invalid message: {msg.data}')

    async def broadcast(self, packet):
        for conn in self.connections:
            await conn.send_json(packet)

    async def handle_message(self, payload: dict):
        op = payload.get('op')
        if not op:
            log.error('No op. Invalid message.')
            return
        if not isinstance(op, str):
            log.error('Invalid op type. Expected str.')

        handler = getattr(self, f'op_{op}', default=None)
        if not handler:
            log.error(f'No handler found for op {op}')
            return

        data = payload.get('data')
        log.debug(f'Handling op {op} with data {data}')
        await handler(data)

    def generate_key(self):
        token = ''
        while (not token) or (token in self.connections):
            token = ''.join(random.choice(CHARACTERS) for i in range(40))
        
        return token

class StreamView():
    def __init__(self, config):
        self.config = config

    async def get_ws(self, request):
        pass
