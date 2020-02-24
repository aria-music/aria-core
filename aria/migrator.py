from pathlib import Path
import asyncio

class Migrator():
    def __init__(self, manager, playlist):
        self.manager = manager
        self.playlist = playlist
        self.loop = asyncio.get_event_loop()

    async def run(self):
        for pl in Path("playlists").iterdir():
            if not pl.stem.startswith("Likes"):
                await self.playlist.create(pl.stem)
            with pl.open("r") as f:
                for uri in f:
                    self.loop.create_task(self.uri_do(pl.stem, uri))
                
    async def uri_do(self, pl, uri):
        if uri.startswith("gpm:store"):
            return
        if uri.startswith("http"):
            return

        e = await self.manager.resolve(uri)
        if e:
            if pl == "Likes":
                for i in e:
                    await self.playlist.like(i.uri)
            else:
                await self.playlist.add_to_playlist(pl, e)
