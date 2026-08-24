from app.domains.auth import models as auth_models
from app.domains.generation import models as generation_models
from app.domains.generation.cache import GenerationCache
from app.domains.generation.providers.base import GenerationError, ProviderResponse
from app.domains.generation.service import execute_generation
from app.domains.projects import models as project_models
from tests.utils import build_test_client


class _FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, prompt: str, model: str) -> ProviderResponse:
        self.call_count += 1
        return ProviderResponse(provider=self.name, model=model, content="hi there", tokens_used=5, latency_ms=1)


class _FakeCacheClient:
    def __init__(self, raise_on_get: bool = False, raise_on_set: bool = False) -> None:
        self.store: dict[str, str] = {}
        self.raise_on_get = raise_on_get
        self.raise_on_set = raise_on_set

    def get(self, key: str) -> str | None:
        if self.raise_on_get:
            raise ConnectionError("redis is down")
        return self.store.get(key)

    def setex(self, key: str, ttl_seconds: int, value: str) -> None:
        if self.raise_on_set:
            raise ConnectionError("redis is down")
        self.store[key] = value

    def delete(self, key: str) -> None:
        self.store.pop(key, None)


def _make_user_and_project(db):
    user = auth_models.User(email="owner@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    project = project_models.Project(name="Proj A", owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return user, project


def test_cache_miss_calls_provider_and_writes_cache() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)
        provider = _FakeProvider()
        cache = GenerationCache(_FakeCacheClient(), default_ttl_seconds=60)

        response = execute_generation(
            db, project_id=project.id, created_by=user.id,
            prompt="say hi", model="mock-model", provider=provider, cache=cache,
        )

        assert response.content == "hi there"
        assert response.cache_hit is False
        assert provider.call_count == 1
        assert len(cache._client.store) == 1
    finally:
        db.close()


def test_cache_hit_skips_provider_call() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)
        provider = _FakeProvider()
        cache = GenerationCache(_FakeCacheClient(), default_ttl_seconds=60)

        first = execute_generation(
            db, project_id=project.id, created_by=user.id,
            prompt="say hi", model="mock-model", provider=provider, cache=cache,
        )
        second = execute_generation(
            db, project_id=project.id, created_by=user.id,
            prompt="say hi", model="mock-model", provider=provider, cache=cache,
        )

        assert first.cache_hit is False
        assert second.cache_hit is True
        assert second.content == "hi there"
        assert provider.call_count == 1  # second call never touched the provider

        responses = db.query(generation_models.GenerationResponse).all()
        assert len(responses) == 2  # both generations are still persisted
    finally:
        db.close()


def test_different_prompt_is_a_cache_miss() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)
        provider = _FakeProvider()
        cache = GenerationCache(_FakeCacheClient(), default_ttl_seconds=60)

        execute_generation(
            db, project_id=project.id, created_by=user.id,
            prompt="say hi", model="mock-model", provider=provider, cache=cache,
        )
        second = execute_generation(
            db, project_id=project.id, created_by=user.id,
            prompt="say something else", model="mock-model", provider=provider, cache=cache,
        )

        assert second.cache_hit is False
        assert provider.call_count == 2
    finally:
        db.close()


def test_no_cache_behaves_like_before() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)
        provider = _FakeProvider()

        response = execute_generation(
            db, project_id=project.id, created_by=user.id,
            prompt="say hi", model="mock-model", provider=provider, cache=None,
        )

        assert response.cache_hit is False
        assert provider.call_count == 1
    finally:
        db.close()


def test_cache_lookup_failure_falls_back_to_provider() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)
        provider = _FakeProvider()
        cache = GenerationCache(_FakeCacheClient(raise_on_get=True), default_ttl_seconds=60)

        response = execute_generation(
            db, project_id=project.id, created_by=user.id,
            prompt="say hi", model="mock-model", provider=provider, cache=cache,
        )

        assert response.cache_hit is False
        assert provider.call_count == 1
    finally:
        db.close()


def test_cache_write_failure_does_not_fail_the_request() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)
        provider = _FakeProvider()
        cache = GenerationCache(_FakeCacheClient(raise_on_set=True), default_ttl_seconds=60)

        response = execute_generation(
            db, project_id=project.id, created_by=user.id,
            prompt="say hi", model="mock-model", provider=provider, cache=cache,
        )

        assert response.content == "hi there"
        assert response.cache_hit is False
    finally:
        db.close()


def test_provider_failure_is_not_cached() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)

        class _AlwaysFailProvider:
            name = "fake"

            def generate(self, prompt: str, model: str) -> ProviderResponse:
                raise GenerationError("nope")

        cache = GenerationCache(_FakeCacheClient(), default_ttl_seconds=60)

        try:
            execute_generation(
                db, project_id=project.id, created_by=user.id,
                prompt="say hi", model="mock-model", provider=_AlwaysFailProvider(), cache=cache,
            )
        except GenerationError:
            pass

        assert cache._client.store == {}
    finally:
        db.close()
