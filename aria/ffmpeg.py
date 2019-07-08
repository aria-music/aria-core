import subprocess
from logging import getLogger

log = getLogger(__name__)


class FFMpegPlayer():
    def __init__(self, opus_encoder):
        self.opus = opus_encoder
        self.ffmpeg = None

    def create(self, filename):
        log.debug(f'Create FFMpeg for file: {filename}')
        self.kill()
        try:
            self.ffmpeg = subprocess.Popen(
                [
                    'ffmpeg',
                    '-i', filename,
                    '-nostdin',
                    '-f', 's16le',
                    '-ar', '48000',
                    '-ac', '2',
                    '-vn',
                    '-loglevel', 'quiet',
                    'pipe:1'
                ],
                stdout=subprocess.PIPE
            )
            log.debug('FFMpeg created!')
        except:
            log.error('Failed to start ffmpeg: ', exc_info=True)

    def kill(self):
        if self.ffmpeg:
            self.ffmpeg.kill()
            self.ffmpeg = None

    def read(self):
        ret = b''
        if self.ffmpeg:
            ret = self.ffmpeg.stdout.read(self.opus.FRAME_SIZE)
        return ret if len(ret) == self.opus.FRAME_SIZE else b''
