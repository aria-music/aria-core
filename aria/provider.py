class MediaSourceManager():
    def __init__(self, config):
        self.config = config
        self.providers = [] # or {}? idk

    def resolve(self, uri):
        pass

    def search(self, query, provider):
        pass
        # search returns EntryOverview obj

    def search_all(self, query):
        pass
