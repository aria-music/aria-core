import asyncio
import logging

import aiohttp_cors
from aiohttp import web

from aria.auth import AuthenticateManager
from aria.config import Config
from aria.database import Database
from aria.ping import ping
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
logging.getLogger('aiohttp').setLevel(logging.ERROR)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    config = Config()
    log.info("Config loaded:")
    log.info(f"  Player socket: {config.player_socket}")
    log.info(f"  Stream socket: {config.stream_socket}")
    log.info(f"  Database endpoint: {config.db_endpoint}")
    log.info(f"  Cache directory: {config.cache_dir}")

    Database(config.db_endpoint)
    auth = AuthenticateManager(config)

    player = PlayerView(config, auth)
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

    player_app.router.add_route('GET', '/ping', ping)
    player_app.router.add_routes([
        web.get("/auth", auth.get_is_valid_invite),
        web.get("/auth/{provider}/register", auth.get_register_url),
        web.get("/auth/{provider}/login", auth.get_login_url),
        web.get("/auth/{provider}/register/callback", auth.get_register_callback),
        web.get("/auth/{provider}/login/callback", auth.get_login_callback)
    ])
    
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
