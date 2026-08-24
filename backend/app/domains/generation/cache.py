

from __future__ import annotations

import hashlib
from typing import Protocol

from app.core.config import settings


class CacheClient(Protocol):


    def get(self, key: str) -> str | bytes | None: ...
    def setex(self, key: str, ttl_seconds: int, value: str) -> None: ...
    def delete(self, key: str) -> None: ...


def build_redis_client() -> CacheClient:
    import redis

    return redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)


class GenerationCache:
    def __init__(self, client: CacheClient, *, default_ttl_seconds: int = settings.cache_ttl_seconds) -> None:
        self._client = client
        self.default_ttl_seconds = default_ttl_seconds

    def build_key(self, prompt: str, model: str, **params: object) -> str:
        # NUL-separated before hashing so e.g. prompt="ab", model="c" can't
        # collide with prompt="a", model="bc" via naive concatenation.
        # **params sorted so kwarg order never changes the key.
        canonical_params = "&".join(f"{k}={params[k]}" for k in sorted(params))
        raw = f"{model}\x00{prompt}\x00{canonical_params}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"gen:{digest}"

    def get(self, key: str) -> str | None:
        value = self._client.get(key)
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else value

    def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        self._client.setex(key, ttl_seconds or self.default_ttl_seconds, value)

    def invalidate(self, key: str) -> None:
        self._client.delete(key)
