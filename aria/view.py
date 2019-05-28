from aiohttp import web, WSMsgType
from logging import getLogger

log = getLogger(__name__)


class PlayerView():
    def __init__(self, config):
        self.config = config

        self.connections = {}

    async def get_ws(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        log.debug(f"Connected to {request.remote}")

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                msg.json

    async def broadcast(self, packet):
        for conn in self.connections:
            await conn.send_json(packet)

class StreamView():
    def __init__(self, config):
        self.config = config

    async def get_ws(self, request):
        pass
