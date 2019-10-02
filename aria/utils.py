import asyncio
import json
import random
import subprocess
import re
from functools import partial
from logging import getLogger
from pathlib import Path
from string import ascii_letters, digits

from aria.models import EntryOverview

CHARACTERS = ascii_letters + digits
KEY_LENGTH = 40

log = getLogger(__name__)
volume_match = re.compile(r"max_volume: (-?\d+\.\d+) dB")


def generate_key(length:int=KEY_LENGTH):
    return ''.join(random.choice(CHARACTERS) for i in range(length))

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
        log.info(f'Got max_volume: {ret}')
    except:
        log.error('Failed to get max_volume:', exc_info=True)
        
    return ret or 0
