import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from inspect import signature
from logging import getLogger
import uuid

from aiohttp import WSMsgType, web

from aria.auth import Auth
from aria.manager import MediaSourceManager
from aria.migrator import Migrator
from aria.player import Player
from aria.playlist import PlaylistManager
from aria.utils import (
    get_pretty_object, get_token_from_cookie, get_token_from_header, json_dump)

log = getLogger(__name__)


"""
APIs

Events
------
event_player_state_change
event_queue_change
event_playlists_change
event_playlist_entry_change

Operations
----------
op_search (query, [provider])
op_playlists
op_playlist (name)
op_create_playlist (name)
op_delete_playlist (name)
op_add_to_playlist (name, uri)
op_remove_from_playlist (name, uri)
op_like (uri)
op_play (uri, [playlist, head]) uri または playlist のどちらか必要
op_pause
op_resume
op_skip
op_skip_to (index, uri)
op_queue (uri, [playlist, head]) uri または playlist のどちらか必要
op_state
op_shuffle
op_repeat (uri, [count])
op_clear_queue
op_remove (uri, index)
op_list_queue
op_edit_queue (queue)
op_token
"""


class PlayerView():
    def __init__(self, config, auth):
        self.config = config
        self.auth: Auth = auth
        # TODO: completely remove token and key
        self.loop = asyncio.get_event_loop()
        self.pool = ThreadPoolExecutor(max_workers=4)

        self.manager = MediaSourceManager(self.config)
        self.playlist = PlaylistManager(self, self.config, self.manager)
        self.player = Player(self, self.manager)

        self.connections = {}

    async def get_ws(self, request: web.Request):
        # check token
        log.debug(f"cookie: {request.cookies}")
        token = get_token_from_cookie(request) or get_token_from_header(request)
        if not token or not await self.auth.is_valid_token(token):
            log.error(f"Token not found or invalid: {token}")
            raise web.HTTPForbidden()

        await self.kill_current_session(token)

        session = str(uuid.uuid4())
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self.connections[session] = ws

        # initial events
        self.loop.create_task(self.on_open_message(ws, session))

        log.debug(f"New player session: {session}")
        log.debug(f'Current player: {len(self.connections)} connections')

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    json_message = msg.json()
                except:
                    log.error(f'Invalid message: {msg.data}')
                    continue
                    
                self.loop.create_task(self.handle_message(json_message, ws))
        
        log.info(f"Player session closed: {session}")
        await self.kill_current_session(session)
        return ws

    async def kill_current_session(self, session: str) -> None:
        current = self.connections.pop(session, None)
        if current != None:
            log.info("Killing current session...")
            await current.close()

    async def post_control(self, request):
        try:
            json_message = await request.json()
        except:
            log.error("Invalid message!")
            return web.Response(status=400)
            
        token = json_message.get('token')
        if not token or not await self.auth.is_valid_token(token):
            log.error("Invalid token!")
            return web.Response(status=403)
        
        ret = await self.handle_message(json_message)
        if ret:
            return web.json_response(ret)

        return web.Response()

    async def on_open_message(self, ws, key):
        await self.send_json(key, ws, enclose_packet('hello', key=key))
        await self.send_json(key, ws, enclose_packet('event_queue_change', {'queue': await self.player.list()}))
        await self.send_json(key, ws, enclose_packet('event_player_state_change', await self.player.enclose_state()))
        await self.send_json(key, ws, enclose_packet('event_playlists_change', {"playlists": await self.playlist.enclose_playlists()}))

    async def broadcast(self, packet):
        log.debug(f'Broadcasting: {str(get_pretty_object(packet))}')
        for key, ws in self.connections.items():
            self.loop.create_task(self.send_json(key, ws, packet))
    
    async def send_json(self, key, ws, json):
        if ws.exception() != None or ws.closed:
            log.info('Deleting closed connection...')
            self.delete_connection(key)
        else:
            try:
                await ws.send_json(json, dumps=json_dump)
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

        log.debug(f'Current player: {len(self.connections)} connections')

    async def handle_message(self, payload:dict, ws=None):
        op = payload.get('op')
        key = payload.get('key')
        postback = payload.get('postback') or ""
        data = payload.get('data')

        if not isinstance(op, str):
            log.error(f'Invalid op type. Expected str: {op}')
            return

        if isinstance(postback, str):
            postback = postback[:100]
        else:
            log.error(f"postback is not a string. Ignore: {postback}")
            postback = ""
        
        handler = getattr(self, f'op_{op}', None)
        if not handler:
            log.error(f'No handler found for op {op}')
            return

        reqs = signature(handler).parameters
        params = {}

        if 'ws' in reqs:
            params['ws'] = ws
        if 'key' in reqs:
            params['key'] = key or ""
        if 'data' in reqs:
            params['data'] = data or {}
        if 'pre' in reqs:
            params['pre'] = partial(enclose_packet, key=key)

        log.debug(f'Handling op {op} with data {data}')
        ret = await handler(**params)
        if ret:
            ret = { 'postback': postback, **ret }

        if ws != None and ret: # bool(ws) sucks
            await self.send_json(key, ws, ret)

        log.debug(f'Returning {str(get_pretty_object(ret))}')
        log.info(f'task op {op} done.')
        return ret
    
    # Event callbacks
    # Better using EventEmitter?
    
    def on_player_state_change(self):
        log.debug('State changed. Broadcasting...')
        self.loop.create_task(self.event_player_state_change())

    async def event_player_state_change(self):
        await self.broadcast(enclose_packet('event_player_state_change', await self.player.enclose_state()))

    def on_queue_change(self):
        log.debug('Queue changed. Broadcasting...')
        self.loop.create_task(self.event_queue_change())

    async def event_queue_change(self):
        ret = {
            'queue': await self.player.list()
        }
        await self.broadcast(enclose_packet('event_queue_change', ret))

    def on_playlists_change(self):
        log.debug('Playlists changed. Broadcasting...')
        self.loop.create_task(self.event_playlists_change())

    async def event_playlists_change(self):
        ret = {
            'playlists': await self.playlist.enclose_playlists()
        }
        await self.broadcast(enclose_packet('event_playlists_change', ret))

    def on_playlist_entry_change(self, playlist_name):
        log.debug(f'Playlist {playlist_name} changed. Broadcasting...')
        self.loop.create_task(self.event_playlist_entry_change(playlist_name))

    async def event_playlist_entry_change(self, playlist_name):
        ret = {
            'name': playlist_name
        }
        await self.broadcast(enclose_packet('event_playlist_entry_change', ret))

    def on_queue_empty(self):
        log.debug('Queue is empty. Adding from Likes list...')
        self.loop.create_task(self.do_on_queue_empty())

    async def do_on_queue_empty(self):
        to_add = await self.playlist.get_random_entry()
        if to_add:
            await self.player.queue.add_entry(await self.manager.resolve_playable(to_add))

    def on_entry_removed(self, entry):
        pass
    
    # Operation handlers

    async def op_search(self, data):
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
        
        try_resolve = await self.manager.resolve(query)
        ret = try_resolve or await self.manager.search(query, provider)
        return enclose_packet('search', ret)
        
    async def op_playlists(self):
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
            'playlists': await self.playlist.enclose_playlists()
        }
        return enclose_packet('playlists', ret)

    async def op_playlist(self, data):
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
        
        if name == "Likes":
            pl = await self.playlist.get_likes()
        elif name == "History":
            pl = {
                "name": "History",
                "entries": await self.playlist.history.get_entries()
            }
        else:
            pl = await self.playlist.get_playlist(name)
            
        if not pl:
            log.error(f'No playlist found for {name}')
            return

        return enclose_packet('playlist', pl)

    async def op_create_playlist(self, data):
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

        if name in ["Likes, History"]:
            log.error("You can't")
            return
        await self.playlist.create(name)

    async def op_delete_playlist(self, data):
        name = data.get('name')
        if not name:
            log.error('No name found in data')
            return
        
        await self.playlist.delete(name)

    async def op_add_to_playlist(self, data):
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

        resolved = await self.manager.resolve(uri)
        if name == "Likes":
            for e in resolved:
                await self.playlist.like(e.uri)
            self.on_player_state_change()
        elif name == "History":
            return
        else:
            await self.playlist.add_to_playlist(name, resolved)

    async def op_remove_from_playlist(self, data):
        name = data.get('name')
        uri = data.get('uri')
        if not name:
            log.error('name not found in data')
            return
        if not uri:
            log.error('uri not found in data')
            return

        if name == "Likes":
            await self.playlist.dislike(uri)
            self.on_player_state_change()
        else:
            await self.playlist.remove_from_playlist(name, uri)

    async def op_like(self, data):
        uri = data.get('uri')
        if not uri:
            log.error('uri not found in data')
            return

        # entries = await self.manager.resolve(uri)
        # if not entries:
        #     log.error('No entry.')
        #     return
        
        # for e in entries:
        liked = await self.playlist.is_liked(uri)
        if liked:
            log.info(f"Dislike {uri}")
            await self.playlist.dislike(uri)
        else:
            log.info(f"Like {uri}")
            await self.playlist.like(uri)

        self.on_player_state_change()
        self.on_queue_change()

    async def op_play(self, data):
        """
        {
            "op": "play",
            "key": key,
            "data": {
                "uri": [] or str
            }
        }

        Returns
        -------
        None
        """
        # await self.player.queue.clear()
        await self.op_queue({ **data, 'head': True })
        await self.player.skip()

    async def op_pause(self):
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

    async def op_resume(self):
        await self.player.resume()

    async def op_skip(self):
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

    async def op_skip_to(self, data):
        index = data.get('index')
        uri = data.get('uri')
        if index == None:
            log.error('Index not found in data')
        if not uri:
            log.error('Uri not found in data')

        await self.player.queue.seek(uri, index)
        await self.player.skip()

    async def op_queue(self, data):
        """
        {
            "op": "queue",
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
        head = data.get('head')
        playlist = data.get('playlist')
        if not playlist and not uri:
            log.error('Uri or playlist is needed.')

        if playlist:
            pl = await self.playlist.get_playlist(playlist)
            if pl:
                await self.player.queue.add_entry(await self.manager.resolve_playable([e["uri"] for e in pl["entries"]]), head=head or False)
            else:
                log.error('Playlist not found.')
        else:
            await self.player.add_entry(uri, head=head or False)
    
    async def op_state(self):
        return enclose_packet('state', await self.player.enclose_state())

    async def op_shuffle(self):
        await self.player.queue.shuffle()

    async def op_repeat(self, data):
        uri = data.get('uri')
        count = data.get('count')
        if not uri:
            log.error('Uri not found in data')

        await self.player.repeat(uri, min(count or 1, 100))

    async def op_clear_queue(self):
        await self.player.queue.clear()

    async def op_remove(self, data):
        uri = data.get('uri')
        index = data.get('index')
        if not uri:
            log.error('Uri not found in data')
            return
        if index == None:
            log.error('Index not found in data')
            return

        await self.player.queue.remove(uri, index)

    async def op_list_queue(self):
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
            'queue': [item.as_dict() for item in await self.player.list()]
        }

        return enclose_packet('list_queue', ret)

    async def op_edit_queue(self, data):
        edited = data.get('queue')
        if not isinstance(edited, list):
            log.error('Invalid type for queue')
            return

        await self.player.queue.assign(edited)

    async def op_update_db(self, data):
        gpm = self.manager.providers.get("gpm")
        if not gpm:
            log.error("No gpm provider")
            return

        user = data.get('user')
        if not user:
            log.error("No user provided")
            return
            
        await gpm.update(user=user)

    async def op_token(self):
        return enclose_packet('token', { 'token': await self.auth.get_token(persist=True) })

    async def op_invite(self):
        return enclose_packet('invite', { 'invite': await self.auth.get_invite() })

    async def op_migrate(self):
        mig = Migrator(self.manager, self.playlist)
        await mig.run()

def enclose_packet(type, data=None, key=None):
    ret = {
        'type': type
    }
    if key:
        ret['key'] = key
    if data:
        ret['data'] = data
    
    return ret
