import asyncio
from aiohttp import web, WSMsgType
from logging import getLogger
from functools import partial
from inspect import signature

from .utils import generate_key
from aria.manager import MediaSourceManager
from aria.playlist import PlaylistManager
from aria.player import Player

log = getLogger(__name__)


class PlayerView():
    def __init__(self, config):
        self.config = config
        self.loop = asyncio.get_event_loop()

        self.manager = MediaSourceManager(self.config)
        self.playlist = PlaylistManager(self.config, self.manager)
        self.player = Player(self.manager)

        self.connections = {}

    async def on_player_state_change(self):
        pass
        # await self.broadcast()

    async def get_ws(self, request):
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)

        key = generate_key()
        while key in self.connections:
            key = generate_key()

        self.connections[key] = ws
        await ws.send_json(enclose_packet(key, 'hello'))

        log.debug("Connected!")

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    self.loop.create_task(self.handle_message(ws, msg.json()))
                except:
                    log.error(f'Invalid message: {msg.data}')

        return ws

    async def broadcast(self, packet):
        for conn in self.connections.values():
            await conn.send_json(packet)

    async def handle_message(self, ws, payload: dict):
        op = payload.get('op')
        key = payload.get('key')
        data = payload.get('data')

        if not isinstance(op, str):
            log.error(f'Invalid op type. Expected str: {op}')
            return
        
        if not isinstance(key, str) or key not in self.connections:
            log.error(f'Invalid key: {key}')
            return

        handler = getattr(self, f'op_{op}', None)
        if not handler:
            log.error(f'No handler found for op {op}')
            return

        encloser = partial(enclose_packet, key)
        reqs = signature(handler).parameters
        params = {}

        if 'ws' in reqs:
            params['ws'] = ws
        if 'key' in reqs:
            params['key'] = key
        if 'data' in reqs:
            params['data'] = data

        log.debug(f'Handling op {op} with data {data}')
        ret = await handler(encloser, **params)
        if ret:
            await ws.send_json(ret)

    async def op_search(self, enc, data):
        """
        {
            "op": "search",
            "key": KEYSTRING,
            "data": {
                "query": QUERYSTRING,
                "provider"?: PROVIDERSTRING
            }
        }

        Returns
        -------
        {
            "res": "search",
            "data": [
                {
                    "source": "gpm",
                    "title": "Region - Mili",
                    "uri": "gpm:track:be223a86-fd8d-3120-ad84-77c81f784865",
                    "thumbnail": "",
                    "entry": {
                        "song_id": "be223a86-fd8d-3120-ad84-77c81f784865",
                        "title": "Region",
                        "artist": "Mili",
                        "album": "Rightfully",
                        "albumArtUrl": ""
                    }
                },
                {
                    "source": "youtube",
                    "title": "Goblin Slayer OP/Opening - Rightfully / Mili [Full]",
                    "uri": "https://www.youtube.com/watch?v=7z4WJAEG3u8",
                    "thumbnail": "https://i.ytimg.com/vi/7z4WJAEG3u8/hqdefault.jpg",
                    "entry": null
                }
            ]
        }
        """
        query = data.get('query')
        provider = data.get('provider')
        if not query: # TODO: check spaces string
            log.error('Invalid query.')
            return
        
        ret = await self.manager.search(query, provider)
        return enc('search', [item.as_dict() for item in ret])
        
    async def op_playlists(self, enc, data):
        """
        {
            "op": "playlists",
            "key": KEY
        }

        Returns
        -------
        {
            "res": "playlists",
            "data": {
                "playlists: [
                    "pl1", "pl2", ...
                ]
            }
        }
        """

        ret = {
            'playlists': self.playlist.list
        }
        return enc('playlists', ret)

    async def op_playlist(self, enc, data):
        """
        {
            "op": "playlist",
            "key": KEY,
            "data": {
                "name": playlistname
            }
        }

        Returns
        -------
        {
            "ret": "playlist",
            "data": {
                "name": playlistname,
                "entries": [

                ]
            }
        }
        """
        name = data.get('name')
        if not name:
            log.error('No name in request packet.')
            return

        pl = self.playlist.get_playlist(name)
        if not pl:
            log.error(f'No playlist found for {name}')
            return

        ret = {
            'name': name,
            'entries': [item.as_dict() for item in await pl.get_entries()]
        }
        return enc('playlist', ret)

    async def op_create_playlist(self, enc, data):
        """
        {
            "op": "create_playlist",
            "key": key,
            "data": {
                "name": playlistname
            }
        }

        Returns
        -------
        None # will change
        """
        name = data.get('name')
        if not name:
            log.error('No name found in packet')
            return

        await self.playlist.create(name)

    async def op_add_to_playlist(self, enc, data):
        """
        {
            "op": "add_to_playlist",
            "key": key,
            "data" {
                "name": playlistname
                "uri": uri
            }
        }

        Returns
        -------
        None # will
        """

        name = data.get('name')
        if not name:
            log.error("name not found in request packet")
            return

        uri = data.get('uri')
        if not uri:
            log.error('URI not found in request packet')
            return

        pl = self.playlist.get_playlist(name)
        if not pl:
            log.error(f'No playlist found for {name}')
            return

        pl.add(uri)

    # async def op_play(self, enc):
    #     """
    #     {
    #         "op": "play",
    #         "key": key
    #     }

    #     Returns
    #     -------
    #     None
    #     """

    #     await self.player.play()

    async def op_pause(self, enc):
        """
        {
            "op": "pause",
            "key": key
        }

        Returns
        -------
        None
        """

        await self.player.pause()

    async def op_resume(self, enc):
        await self.player.resume()

    async def op_skip(self, enc):
        """
        {
            "op": "skip",
            "key": "key"
        }

        Returns
        -------
        None
        """

        await self.player.skip()

    async def op_play(self, enc, data):
        """
        {
            "op": "play",
            "key": key,
            "data": {
                "uri": string or [strings]
            }
        }

        Returns
        -------
        None
        """

        uri = data.get('uri')
        if not uri:
            log.error('URI not found in request packet')
            return

        await self.player.add_entry(uri)

    async def op_list_queue(self, enc):
        """
        {
            "op": "list_queue",
            "key": key
        }

        Returns
        -------
        {
            "ret": "list_queue",
            "data": {
                "queue": [
                    entryoverviews
                    ...
                ]
            }
        }
        """

        ret = {
            'queue': [item.as_dict() for item in self.player.list]
        }

        return enc('list_queue', ret)

def enclose_packet(key, res, data=None):
    return {
        'type': res,
        'key': key,
        'data': data
    }
