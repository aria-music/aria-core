from collections import deque

class Playlist():
    def __init__(self, provider):
        self.provider = provider
        self.queue = deque()
        
    def get_next(self):
        ret = None
        try:
            ret = self.queue.pop()
        except:
            pass

        return ret

    def add_entry(self, uri, head=False):
        pass

    def remove_entry(self, entry):
        pass
