class Provider():
    TYPE = 'base'

    def __init__(self):
        raise NotImplementedError()

    def resolve(self, uri):
        raise NotImplementedError()

    def search(self, query):
        raise NotImplementedError()
