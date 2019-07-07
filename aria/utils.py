import json
import random
from pathlib import Path
from string import ascii_letters, digits
from functools import partial
from aria.models import EntryOverview

CHARACTERS = ascii_letters + digits
KEY_LENGTH = 40


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
