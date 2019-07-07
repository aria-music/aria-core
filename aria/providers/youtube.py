import asyncio
from logging import getLogger
from typing import Optional, Sequence

from aiohttp import ClientSession

from aria.models import EntryOverview, Provider
from aria.exceptions import ProviderNotReady

log = getLogger(__name__)


class YoutubeProvider(Provider):
    name = 'youtube'
    can_search = True

    endpoint = 'https://www.googleapis.com/youtube/v3/search'
    default_params = {
        'part': 'id,snippet',
        'maxResults': 15,
        'type': 'video',
    }

    def __init__(self, *, api_key:str=None):
        self.loop = asyncio.get_event_loop()
        self.session = ClientSession()
        self.api_key = api_key

        if not self.api_key:
            log.critical('API KEY is missing!')
            raise ProviderNotReady()
        
        self.default_params = {**self.default_params, 'key': self.api_key}
    
    async def search(self, keyword:str) -> Sequence[EntryOverview]:
        ret = []
        res = await self.youtube_api(params={'q': keyword})

        # should we validate with lib?
        if 'items' in res:
            for item in res['items']:
                try:
                    video_id = item['id']['videoId']
                    title = item['snippet']['title']
                    thumbnail = item['snippet']['thumbnails']['high']['url']
                except:
                    log.error('missing key: ', exc_info=True)
                
                ret.append(EntryOverview(self.name, title, f'https://www.youtube.com/watch?v={video_id}', thumbnail, None))

        return ret
    async def resolve_playable(self, uri, cache_dir):
        # search-only provider
        return

    async def resolve(self, uri:str) -> Optional[EntryOverview]:
        # search-only provider
        return

    async def youtube_api(self, params={}) -> Optional[dict]:
        ret = None
        try:
            async with self.session.get(self.endpoint, params={**self.default_params, **params}) as res:
                ret = await res.json()
                log.debug(ret)
        except:
            log.error(f'Failed to communicate with YouTube API ({params}): ', exc_info=True)

        return ret
