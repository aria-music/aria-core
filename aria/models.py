from typing import Optional, Sequence
from enum import IntEnum

class PlayerState(IntEnum):
    STOPPED = 0
    PLAYING = 1
    PAUSED  = 2

class EntryOverview():
    def __init__(self, source:str, title:str,
                    uri:str, thumbnail:str=None,
                    thumbnail_small:str=None, entry:dict=None):
        self.source = source
        self.title = title
        self.uri = uri
        self.thumbnail = thumbnail or ''
        self.thumbnail_small = thumbnail_small or self.thumbnail
        self.entry = entry
        self.is_liked = False

    def as_dict(self):
        return {
            "source": self.source,
            "title": self.title,
            "uri": self.uri,
            "thumbnail": self.thumbnail,
            "thumbnail_small": self.thumbnail_small,
            "is_liked": self.is_liked,
            "entry": self.entry if self.source == 'gpm' else None # temporary
        }


class PlayableEntry():
    def __init__(self):
        self.title = None
        self.duration = None
        self.file = None
    
    async def download(self):
        raise NotImplementedError()


class Provider():
    name:str = '__base__'
    resolve_prefixes:Optional[Sequence[str]] = None
    can_search:bool = False

    async def search(self, query:str) -> Sequence[EntryOverview]:
        raise NotImplementedError()

    async def resolve_playable(self, uri:str, cache_dir:str):
        raise NotImplementedError()

    async def resolve(self, uri:str) -> Sequence[EntryOverview]:
        raise NotImplementedError()

    async def resolve_playable(self, uri:str) -> Sequence[PlayableEntry]:
        raise NotImplementedError()
