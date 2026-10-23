import hashlib
import secrets
from enum import StrEnum

API_KEY_PREFIX = "labdocs_"
API_KEY_BYTES = 32


class Scope(StrEnum):
    READ = "read"
    WRITE = "write"


def generate_api_key() -> str:
    """Generate a new opaque API key. The plaintext is shown to the user once."""
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(API_KEY_BYTES)}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for storage and lookup."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def effective_scopes(scope: str) -> list[Scope]:
    """Return the scopes a key actually has. A write key can also read."""
    if scope == Scope.WRITE:
        return [Scope.READ, Scope.WRITE]
    return [Scope.READ]


def has_scope(scope: str, required: Scope) -> bool:
    return required in effective_scopes(scope)
