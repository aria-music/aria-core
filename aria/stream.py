from logging import getLogger
from pathlib import Path
from time import sleep
from typing import Union

from aria import opus
from aria.ffmpeg import FFMpegPlayer

log = getLogger(__name__)

OPUSLIB = ['libopus-0.x64.dll', 'libopus-0.x86.dll', 'libopus.so.0', 'libopus.0.dylib']


class StreamPlayer():
    def __init__(self, player):
        self.player = player

        self.opus = None
        self.create_opus()
        self.ffmpeg = FFMpegPlayer(self.opus)
        self.is_paused = False
        self.position = 0.00

    @property
    def current_position(self):
        return int(self.position)

    # These control command must be runned **synchronously** 
    def play(self, file:Union[str, Path]):
        self.is_paused = True
        file = file if isinstance(file, str) else str(file)
        self.ffmpeg.create(file)
        sleep(0.5) # Ensure ffmpeg start decoding
        self.position = 0
        self.is_paused = False

        # while not self.read():
        #     log.debug('no data')

    def read(self):
        # CALLED FROM OTHER THREAD
        if self.is_paused:
            return b''

        audio = self.ffmpeg.read()
        self.position += 0.02
        # log.debug(f'Audio bytes: {len(audio)}')
        return self.opus.encode(audio, self.opus.SAMPLES_PER_FRAME) if audio else self.play_finished()

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        self.is_paused = True
        self.ffmpeg.kill()

    def play_finished(self):
        # CALLED FROM OTHER THREAD
        self.is_paused = True
        self.player.on_play_finished()
        return b''

    def create_opus(self):
        if opus.is_loaded():
            log.info('system libopus is loaded.')
        else:
            log.info('libopus is not loaded. Start loading...')
            for lib in OPUSLIB:
                opus.load_opus(lib)
                if opus.is_loaded:
                    log.info(f'loaded {lib}')
                    break

        # let Encoder() raises OpusNotReady
        self.opus = opus.Encoder()
