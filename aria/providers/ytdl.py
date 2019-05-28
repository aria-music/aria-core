from .models import Provider

class YoutubeDLProvider(Provider):
    def __init__(self):
        pass

    def resolve(self, uri):
        return super().resolve(uri)

    def search(self, query):
        return super().search(query)
