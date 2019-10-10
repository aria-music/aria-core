from typing import Sequence, Optional

import aiosqlite
from .utils import GPMSong


class StoreManager():
    def __init__(self, db_file=None):
        self.db = db_file or 'config/gpm.sqlite3'

    async def update(self, songs:Sequence[GPMSong], user:str=None) -> None:
        async with aiosqlite.connect(self.db) as db:
            if user:
                await db.execute("DELETE FROM songs WHERE user = ?", (user, ))
            else:
                await db.execute("DROP TABLE IF EXISTS songs")
                await db.execute("""CREATE TABLE IF NOT EXISTS songs (user text,
                                                                  song_id text,
                                                                  title text,
                                                                  artist text,
                                                                  album text,
                                                                  albumArtUrl text)""")
            
            await db.executemany("""INSERT INTO songs VALUES (:user,
                                                              :song_id,
                                                              :title,
                                                              :artist,
                                                              :album,
                                                              :albumArtUrl)""", songs)
            await db.commit()

    async def search(self, keyword:str) -> Sequence[GPMSong]:
        query = f"%{'%'.join(keyword.split())}%"
        res = None
        async with aiosqlite.connect(self.db) as db:
            cur = await db.execute("SELECT * FROM songs WHERE user||' '||title||' '||artist||' '||album LIKE ?", (query, ))
            res = await cur.fetchall()

        return [GPMSong(*song) for song in res]

    async def resolve(self, user, song_id:str) -> Optional[GPMSong]:
        res = None
        async with aiosqlite.connect(self.db) as db:
            cur = await db.execute("SELECT * FROM songs WHERE user = ? AND song_id = ?", (user, song_id))
            res = await cur.fetchall()

        return GPMSong(*res[-1]) if res else None
