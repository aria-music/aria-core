import array
import ctypes
from logging import getLogger

from aria.exceptions import OpusError, OpusNotFound, OpusNotReady

log = getLogger(__name__)
OPUSLIB = ['libopus-0.x86', 'libopus-0.x64', 'libopus.so.0', 'libopus.0.dylib']

FRAME_SIZE = 1024


class OpusEncoder():
    def __init__(self):
        self.opus = None
        self.opus_encoder = None
        self.load_opus()

    def load_opus(self):
        for lib_name in OPUSLIB:
            try:
                self.opus = ctypes.cdll.LoadLibrary(lib_name)
                break
            except:
                pass

        if not self.opus:
            log.critical('Failed to load libopus!')
            raise OpusNotFound()

        try:
            # https://opus-codec.org/docs/opus_api-1.2/index.html

            # C -> Python types
            # char * -> ctypes.c_char_p (byte string b'')
            # * -> ctypes.POINTER(typevar T)
            # struct -> ctypes.Structure

            """
            const char * opus_strerror(int error)
            Converts an opus error code into a human readable string.
            """
            self.opus.opus_strerror.argtypes = [ctypes.c_int]
            self.opus.opus_strerror.restype = ctypes.c_char_p

            """
            OpusEncoder* opus_encoder_create	(	opus_int32 	Fs,
                                                    int 	channels,
                                                    int 	application,
                                                    int * 	error 
                                                )	
            Allocates and initializes an encoder state.
            """
            self.opus.opus_encoder_create.argtypes = [ctypes.c_int,
                                                      ctypes.c_int,
                                                      ctypes.c_int,
                                                      ctypes.POINTER(ctypes.c_int)]
            self.opus.opus_encoder_create.restype = ctypes.POINTER(ctypes.Structure)

            """
            opus_int32 opus_encode	(	OpusEncoder * 	st,
                                        const opus_int16 * 	pcm,
                                        int 	frame_size,
                                        unsigned char * 	data,
                                        opus_int32 	max_data_bytes 
                                    )
            Encodes an Opus frame from floating point input.
            """
            self.opus.opus_encode.argtypes = [ctypes.POINTER(ctypes.Structure),
                                              ctypes.POINTER(ctypes.c_int16),
                                              ctypes.c_int,
                                              ctypes.POINTER(ctypes.c_char_p), # これ c_char_p でええんかな
                                              ctypes.c_int32]
            self.opus.opus_encode.restype = ctypes.c_int32
        except:
            log.critical('Failed to set prototype to libopus functions!')
            raise OpusNotReady()

    def create_encoder(self, sampling_rate:int, channels:int,
                        application:int, error:ctypes.POINTER(ctypes.c_int)):
        ret = ctypes.c_int()
        self.opus_encoder = self.opus.opus_encoder_create(sampling_rate, channels, application, ctypes.byref(ret))
        if not self.opus_encoder:
            msg = self.opus.opus_strerror(ret)
            log.critical(f'Error while creating opus encoder: {msg}')
            raise OpusNotReady()

    def encode(self, pcm:bytes):
        pcm_length = len(pcm)
        encoded = (ctypes.c_char * pcm_length)()
        ret = self.opus.opus_encode(self.opus_encoder, ctypes.cast(pcm, ctypes.POINTER(ctypes.c_int16)),
                                    FRAME_SIZE, encoded, pcm_length)
        
        if ret < 0:
            msg = self.opus.opus_strerror(ret)
            log.error(f'Opus errored: {msg}')
            return b''

        return array.array('b', encoded[:ret]).tobytes()
