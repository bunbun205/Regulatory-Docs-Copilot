from app.core.security import (
    Scope,
    effective_scopes,
    generate_api_key,
    has_scope,
    hash_api_key,
)


def test_generate_api_key_is_prefixed_and_unique() -> None:
    first = generate_api_key()
    second = generate_api_key()
    assert first.startswith("labdocs_")
    assert first != second
    assert len(first) > len("labdocs_")


def test_hash_api_key_is_stable_sha256() -> None:
    key = "labdocs_test-key"
    digest = hash_api_key(key)
    assert digest == hash_api_key(key)
    assert len(digest) == 64
    assert digest != key


def test_effective_scopes() -> None:
    assert effective_scopes("read") == [Scope.READ]
    assert effective_scopes("write") == [Scope.READ, Scope.WRITE]


def test_has_scope() -> None:
    assert has_scope("read", Scope.READ)
    assert not has_scope("read", Scope.WRITE)
    assert has_scope("write", Scope.WRITE)
