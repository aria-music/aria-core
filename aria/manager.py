import asyncio
from logging import getLogger
from typing import Sequence

from aria import providers
from aria.models import EntryOverview

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

    async def resolve(self, uri):
        prefix = uri.split(':')[0]
        provider = self.resolvers.get(prefix)
        if not provider:
            log.error(f'No provider matches for `{prefix}`')
            return

        return await provider.resolve(uri)

    async def search(self, query, provider=None) -> Sequence['EntryOverview']:
        ret = []
        single_provider = self.providers.get(provider)
        if not single_provider:
            log.error(f'Provider `{provider}` not found.')
            return ret

        results, pending = await asyncio.wait([prov.search(query) for prov in single_provider or self.providers.values()],
                                              timeout=10, return_when=asyncio.ALL_COMPLETED)
        log.debug(f'results: {results}, pending: {pending}')
        for res in results:
            try:
                ret += await res
            except:
                log.error('Search failed in provider:\n', exc_info=True)
            
        return ret
