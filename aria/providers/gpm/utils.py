from collections import namedtuple
from aria.exceptions import AriaException


class GPMError(AriaException):
    pass

GPMSong = namedtuple('GPMSong', ('song_id', 'title', 'artist', 'album', 'albumArtUrl'))

def id_to_uri(song_id:str):
    return f'gpm:track:{song_id}'

def uri_to_id(uri:str):
    return uri.split(':')[2]
