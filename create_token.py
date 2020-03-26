import asyncio
import secrets

from tortoise import Tortoise

from aria.auth import TOKEN_LENGTH, Token

token = secrets.token_urlsafe(TOKEN_LENGTH)

async def get_token():
    await Tortoise.init(
        db_url="sqlite://config/token.sqlite3",
        modules={
            "models": [ "aria.auth.models" ]
        }
    )
    await Tortoise.generate_schemas()
    await Token(token=token).save()
    await Tortoise.close_connections()

if __name__ == '__main__':
    asyncio.run(get_token())
    print(token)
