import asyncio
import json
import random
import subprocess
import re
from functools import partial
from logging import getLogger
from pathlib import Path
from string import ascii_letters, digits
from typing import Optional
from aiohttp import web

from aria.models import EntryOverview

CHARACTERS = ascii_letters + digits
KEY_LENGTH = 40

log = getLogger(__name__)
volume_match = re.compile(r"mean_volume: (-?\d+\.\d+) dB")

def get_token_from_cookie(request: web.Request) -> Optional[str]:
    return request.cookies.get("token")

def get_token_from_header(request: web.Request) -> Optional[str]:
    authorization: str = request.headers.get("authorization")
    if authorization:
        a = authorization.split(" ", 1)
        if len(a) != 2 or a[0].lower() != "bearer":
            log.error(f"Invalid Authorization header: {authorization}")
            return None
        
        return a[1]

def get_pretty_object(obj):
    if isinstance(obj, dict):
        ret = {}
        for k, v in obj.items():
            ret[k] = get_pretty_object(v)
        return ret
    elif isinstance(obj, (list, tuple)) and len(obj):
        return f"<{len(obj)} x {type(obj[0])} like {get_pretty_object(obj[0])}>"
    else:
        return obj    

def save_file(filename: str, data: bytes):
    with Path(filename).open('wb') as f:
        f.write(data)

class AriaJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, EntryOverview):
            return obj.as_dict()
        return super().default(obj)

json_dump = partial(json.dumps, cls=AriaJSONEncoder)

async def get_duration(filename):
    ret = None
    try:
        ffprobe = await asyncio.create_subprocess_exec(
            'ffprobe',
            *[
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                filename
            ],
            stdout=subprocess.PIPE
        )
        stdout, _ = await ffprobe.communicate()
        log.debug(stdout)
        ret = float(stdout.decode('utf-8').strip())
        log.info(f'Got duration: {ret}')
    except:
        log.error('Failed to get duration: ', exc_info=True)

    return ret or 0

async def get_volume(filename:str):
    ret = None
    try:
        ffmpeg = await asyncio.create_subprocess_exec(
            'ffmpeg',
            *[
                '-i', filename,
                '-hide_banner',
                '-af', 'volumedetect',
                '-f', 'null',
                '/dev/null'
            ],
            stderr=subprocess.PIPE
        )
        _, stderr = await ffmpeg.communicate()
        log.debug(stderr)
        ret = float(volume_match.findall(stderr.decode('utf-8'))[0])
        log.info(f'Got mean_volume: {ret}')
    except:
        log.error('Failed to get mean_volume:', exc_info=True)
        
    return ret or 0
