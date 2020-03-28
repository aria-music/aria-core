from aiohttp import web

def ping(request: web.Request):
    return web.Response(body="Aria is ok")
