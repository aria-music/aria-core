from collections import namedtuple
from aria.exceptions import AriaException


class GPMError(AriaException):
    pass


# TODO: make GPMSong class
GPMSong = namedtuple('GPMSong', ('user', 'song_id', 'title', 'artist', 'album', 'albumArtUrl', 'is_liked'))

def id_to_uri(song_id:str):
    return f'gpm:track:{song_id}'

def get_song_uri(song: GPMSong, store=False) -> str:
    return f"gpm:{'storeTrack' if store else 'track'}:{song.user}:{song.song_id}"

def uri_to_id(uri:str):
    return uri.split(':')[3]

def uri_to_user(uri:str):
    return uri.split(':')[2]
