from typing import Tuple, Type

from aria.authenticators.models import Authenticator

from .github import GitHubAuthenticator

AUTHENTICATORS: Tuple[Type[Authenticator]] = (
    GitHubAuthenticator,
)
