from typing import Sequence, Optional

import aiosqlite
from .utils import GPMSong


class StoreManager():
    def __init__(self, db_file=None):
        self.db = db_file or 'config/gpm.sqlite3'

    async def update(self, songs:Sequence[GPMSong]) -> None:
        async with aiosqlite.connect(self.db) as db:
            await db.execute("DROP TABLE IF EXISTS songs")
            await db.execute("""CREATE TABLE IF NOT EXISTS songs (song_id text,
                                                                  title text,
                                                                  artist text,
                                                                  album text,
                                                                  albumArtUrl text)""")
            await db.executemany("""INSERT INTO songs VALUES (:song_id,
                                                              :title,
                                                              :artist,
                                                              :album,
                                                              :albumArtUrl)""", songs)
            await db.commit()

    async def search(self, keyword:str) -> Sequence[GPMSong]:
        query = f"%{'%'.join(keyword.split())}%"
        res = None
        async with aiosqlite.connect(self.db) as db:
            cur = await db.execute("SELECT * FROM songs WHERE title||' '||artist||' '||album LIKE ?", (query, ))
            res = await cur.fetchall()

        return [GPMSong(*song) for song in res]

    async def resolve(self, song_id:str) -> Optional[GPMSong]:
        res = None
        async with aiosqlite.connect(self.db) as db:
            cur = await db.execute("SELECT * FROM songs WHERE song_id = ?", (song_id, ))
            res = await cur.fetchall()

        return GPMSong(*res[-1]) if res else None
