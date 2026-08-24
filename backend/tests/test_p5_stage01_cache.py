from app.domains.generation.cache import GenerationCache


class FakeCacheClient:
    """In-memory stand-in for redis.Redis — no real Redis needed for tests."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        self.store[key] = value
        self.ttls[key] = ttl_seconds

    def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.ttls.pop(key, None)


def test_build_key_is_deterministic_for_same_inputs() -> None:
    cache = GenerationCache(FakeCacheClient(), default_ttl_seconds=60)

    key_a = cache.build_key("hello world", "mock-model")
    key_b = cache.build_key("hello world", "mock-model")

    assert key_a == key_b


def test_build_key_differs_for_different_prompt() -> None:
    cache = GenerationCache(FakeCacheClient(), default_ttl_seconds=60)

    key_a = cache.build_key("hello world", "mock-model")
    key_b = cache.build_key("goodbye world", "mock-model")

    assert key_a != key_b


def test_build_key_differs_for_different_model() -> None:
    cache = GenerationCache(FakeCacheClient(), default_ttl_seconds=60)

    key_a = cache.build_key("hello world", "mock-model")
    key_b = cache.build_key("hello world", "gpt-4o-mini")

    assert key_a != key_b


def test_build_key_differs_for_different_params() -> None:
    cache = GenerationCache(FakeCacheClient(), default_ttl_seconds=60)

    key_a = cache.build_key("hello world", "mock-model", temperature=0.0)
    key_b = cache.build_key("hello world", "mock-model", temperature=0.9)

    assert key_a != key_b


def test_get_returns_none_on_miss() -> None:
    cache = GenerationCache(FakeCacheClient(), default_ttl_seconds=60)

    assert cache.get(cache.build_key("hello world", "mock-model")) is None


def test_set_then_get_returns_the_value() -> None:
    cache = GenerationCache(FakeCacheClient(), default_ttl_seconds=60)
    key = cache.build_key("hello world", "mock-model")

    cache.set(key, "cached response")

    assert cache.get(key) == "cached response"


def test_set_uses_default_ttl_when_none_given() -> None:
    client = FakeCacheClient()
    cache = GenerationCache(client, default_ttl_seconds=123)
    key = cache.build_key("hello world", "mock-model")

    cache.set(key, "cached response")

    assert client.ttls[key] == 123


def test_set_uses_explicit_ttl_override() -> None:
    client = FakeCacheClient()
    cache = GenerationCache(client, default_ttl_seconds=123)
    key = cache.build_key("hello world", "mock-model")

    cache.set(key, "cached response", ttl_seconds=999)

    assert client.ttls[key] == 999


def test_invalidate_removes_the_key() -> None:
    cache = GenerationCache(FakeCacheClient(), default_ttl_seconds=60)
    key = cache.build_key("hello world", "mock-model")
    cache.set(key, "cached response")

    cache.invalidate(key)

    assert cache.get(key) is None
