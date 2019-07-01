import random
from pathlib import Path
from string import ascii_letters, digits

CHARACTERS = ascii_letters + digits
KEY_LENGTH = 40


def generate_key(length:int=KEY_LENGTH):
    return ''.join(random.choice(CHARACTERS) for i in range(length))

def save_file(filename:str, data:bytes):
    with Path(filename).open('wb') as f:
        f.write(data)
