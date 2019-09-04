class AriaException(Exception):
    pass

class ProviderError(AriaException):
    pass

class ProviderNotReady(ProviderError):
    pass

class EmptyPlaylist(AriaException):
    pass