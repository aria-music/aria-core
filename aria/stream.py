from pathlib import Path
from typing import Union
from logging import getLogger

from aria.ffmpeg import FFMpegPlayer
from aria.models import PlayerState
from aria import opus
log = getLogger(__name__)

OPUSLIB = ['libopus-0.x64.dll', 'libopus-0.x86.dll', 'libopus.so.0', 'libopus.0.dylib']


class StreamPlayer():
    def __init__(self):
        self.opus = None
        self.ffmpeg = FFMpegPlayer(self.opus)

        self.create_opus()

    def play(self, file:Union[str, Path]):
        file = file if isinstance(file, str) else str(file)
        self.ffmpeg.create(file)

    def read(self):
        audio = self.ffmpeg.read()
        return self.opus.encode(audio, self.opus.SAMPLES_PER_FRAME)

    def stop(self):
        self.ffmpeg.kill()

    def create_opus(self):
        if opus.is_loaded():
            log.info('libopus is loaded.')
        else:
            log.info('libopus is not loaded. Start loading...')
            for lib in OPUSLIB:
                opus.load_opus(lib)
                if opus.is_loaded:
                    log.info(f'loaded {lib}')
                    break

        # let Encoder() raises OpusNotReady
        self.opus = opus.Encoder()
        