import asyncio
from logging import getLogger
from typing import Sequence, Optional

from aria import providers
from aria.models import EntryOverview, PlayableEntry, Provider

log = getLogger(__name__)


class MediaSourceManager():
    def __init__(self, config):
        self.config = config
        self.providers = {}
        self.resolvers = {}
        self.init_providers()

    def init_providers(self):
        for provider in providers.__all__:
            name = provider.name
            prefixes = provider.resolve_prefixes or []
            config = self.config.providers_config.get(name)
            
            try:
                ins = provider(**config) if config else provider()
                if name:
                    self.providers[name] = ins
                for prefix in prefixes:
                    self.resolvers[prefix] = ins
                log.info(f'Initialized provider `{name}`')
            except:
                log.error(f'Failed to initialize provider `{name}`:\n', exc_info=True)

    async def resolve(self, uri) -> Sequence[EntryOverview]:
        provider = self.get_provider(uri)
        return (await provider.resolve(uri)) if provider else []

    async def resolve_playable(self, uri) -> Sequence[PlayableEntry]:
        provider = self.get_provider(uri)
        return (await provider.resolve_playable(uri, self.config.cache_dir)) if provider else []

    def get_provider(self, uri) -> Optional[Provider]:
        prefix = uri.split(':')[0]
        provider = self.resolvers.get(prefix)
        if not provider:
            log.error(f'No provider matches for `{prefix}`')
            return

        return provider

    async def search(self, query, provider=None) -> Sequence['EntryOverview']:
        tophits = []
        items = []
        single_provider = None
        if provider:
            single_provider = self.providers.get(provider)
            if not single_provider:
                log.error(f'Provider `{provider}` not found.')
                return []

        results, pending = await asyncio.wait([prov.search(query) for prov in single_provider or self.providers.values()],
                                              timeout=10, return_when=asyncio.ALL_COMPLETED)
        log.debug(f'results: {results}, pending: {pending}')
        for res in results:
            try:
                search_res = await res
                tophits += search_res[0:2]
                items += search_res[2:]
            except:
                log.error('Search failed in provider:\n', exc_info=True)
            
        return tophits + items
