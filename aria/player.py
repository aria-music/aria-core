import asyncio
from enum import IntEnum

from .playlist import Playlist
from .provider import MediaSourceManager

class PlayerState(IntEnum):
    STOPPED = 0
    PLAYING = 1
    PAUSED  = 2

class Player():
    def __init__(self):
        self.provider = MediaSourceManager()
        self.playlist = Playlist()
        
        self.state = PlayerState.PAUSED

    def play(self):
        pass
    
    def stop(self):
        pass

    def pause(self):
        pass

    def resume(self):
        pass

    # Callbacks
    def on_play_finished(self):
        """
        Should be passed to StreamPlayer
        """
        pass
