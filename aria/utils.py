import asyncio
import json
import random
import subprocess
from functools import partial
from logging import getLogger
from pathlib import Path
from string import ascii_letters, digits

from aria.models import EntryOverview

CHARACTERS = ascii_letters + digits
KEY_LENGTH = 40

log = getLogger(__name__)


def generate_key(length: int = KEY_LENGTH):
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
        ret = int(float(stdout.decode('utf-8').strip()))
    except:
        log.error('Failed to get duration: ', exc_info=True)

    log.info(f'Got duration: {ret}')
    return ret or 0
