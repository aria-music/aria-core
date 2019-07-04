from typing import Optional, Sequence
from enum import IntEnum

class PlayerState(IntEnum):
    STOPPED = 0
    PLAYING = 1
    PAUSED  = 2

class EntryOverview():
    def __init__(self, source:str, title:str,
                    uri:str, thumbnail:str=None,
                    entry:dict=None):
        self.source = source
        self.title = title
        self.uri = uri
        self.thumbnail = thumbnail or ''
        self.entry = entry

    def as_dict(self):
        return {
            "source": self.source,
            "title": self.title,
            "uri": self.uri,
            "thumbnail": self.thumbnail,
            "entry": self.entry
        }


class PlayableEntry():
    def __init__(self):
        self.title = None
        self.duration = None
        self.file = None
    
    async def download(self):
        raise NotImplementedError()


class Provider():
    name:Optional[str] = None
    resolve_prefixes:Optional[Sequence[str]] = None

    async def search(self, query:str) -> Sequence[EntryOverview]:
        raise NotImplementedError()

    async def resolve(self, uri:str) -> Sequence[EntryOverview]:
        raise NotImplementedError()

    async def resolve_playable(self, uri:str) -> Sequence[PlayableEntry]:
        raise NotImplementedError()
