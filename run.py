import asyncio
import logging

import aiohttp_cors
from aiohttp import web

from aria.config import Config
from aria.player_view import PlayerView
from aria.stream_view import StreamView

handler = logging.StreamHandler()
# handler.addFilter(lambda module: module.name.split('.')[0] in ['aria'])

logging.basicConfig(level=logging.DEBUG, format='[{asctime}][{levelname}][{module}][{funcName}] {message}',
                    style='{', handlers=[handler])
log = logging.getLogger()

# Silence loggers
logging.getLogger('aiosqlite').setLevel(logging.ERROR)
logging.getLogger('gmusicapi').setLevel(logging.ERROR)
# logging.getLogger('aiohttp').setLevel(logging.ERROR)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    config = Config()
    
    player = PlayerView(config)
    player_app = web.Application()
    cors = aiohttp_cors.setup(player_app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=False,
            expose_headers="*",
            allow_headers="*"
        )
    })

    player_app.router.add_route('GET', '/', player.get_ws)
    control = cors.add(player_app.router.add_resource('/control'))
    cors.add(control.add_route('POST', player.post_control))
    
    player_app_runner = web.AppRunner(player_app)
    
    stream = StreamView(config, player)
    stream_app = web.Application()
    stream_app.add_routes([web.get('/', stream.get_ws)])
    stream_app_runner = web.AppRunner(stream_app)

    loop.run_until_complete(player_app_runner.setup())
    loop.run_until_complete(stream_app_runner.setup())

    sites = []
    sites.append(web.UnixSite(player_app_runner, config.player_socket))
    sites.append(web.UnixSite(stream_app_runner, config.stream_socket))

    for site in sites:
        loop.run_until_complete(site.start())
    
    log.info('Starting server...')
    loop.run_forever()
