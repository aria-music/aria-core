import asyncio

from aiohttp import web

from aria.config import Config
from aria.view import PlayerView, StreamView

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    config = Config()
    
    player = PlayerView(config)
    player_app = web.Application()
    player_app.add_routes([web.get('/player', player.get_ws)])
    player_app_runner = web.AppRunner(player_app)
    
    stream = StreamView(config)
    stream_app = web.Application()
    stream_app.add_routes([web.get('/stream', stream.get_ws)])
    stream_app_runner = web.AppRunner(stream_app)

    loop.run_until_complete(player_app_runner.setup())
    loop.run_until_complete(stream_app_runner.setup())

    sites = []
    sites.append(web.UnixSite(player_app_runner, config.player_socket))
    sites.append(web.UnixSite(stream_app_runner, config.stream_socket))

    for site in sites:
        loop.run_until_complete(site.start())
        
    loop.run_forever()
