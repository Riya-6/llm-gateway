from app.domains.auth import models as auth_models  # noqa: F401
from app.domains.generation import models as generation_models
from app.domains.generation.provider_router import AllProvidersUnavailableError
from app.domains.generation.providers.base import GenerationError, ProviderResponse
from app.domains.generation.router import get_generation_provider
from app.domains.projects import models as project_models  # noqa: F401
from app.main import app
from tests.utils import build_test_client


def _register_and_login(client, email, password="hunter22"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return login.json()["access_token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _create_project(client, token):
    return client.post("/api/v1/projects", json={"name": "Proj A"}, headers=_auth_header(token)).json()["id"]


class _FakeProvider:
    name = "fake"

    def __init__(self, content: str = "hello there", always_fail: bool = False, unavailable: bool = False) -> None:
        self.content = content
        self.always_fail = always_fail
        self.unavailable = unavailable

    def generate(self, prompt: str, model: str) -> ProviderResponse:
        if self.unavailable:
            raise AllProvidersUnavailableError("nothing available")
        if self.always_fail:
            raise GenerationError("fake failed")
        return ProviderResponse(provider=self.name, model=model, content=self.content, tokens_used=3, latency_ms=1)


def test_generate_happy_path() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "alice@example.com")
    project_id = _create_project(client, token)

    app.dependency_overrides[get_generation_provider] = lambda: _FakeProvider()
    try:
        response = client.post(
            f"/api/v1/projects/{project_id}/generate",
            json={"prompt": "say hi", "model": "mock-model"},
            headers=_auth_header(token),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["provider"] == "fake"
        assert body["content"] == "hello there"
    finally:
        del app.dependency_overrides[get_generation_provider]


def test_generate_returns_502_on_generation_error() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "bob@example.com")
    project_id = _create_project(client, token)

    app.dependency_overrides[get_generation_provider] = lambda: _FakeProvider(always_fail=True)
    try:
        response = client.post(
            f"/api/v1/projects/{project_id}/generate",
            json={"prompt": "say hi", "model": "mock-model"},
            headers=_auth_header(token),
        )
        assert response.status_code == 502
    finally:
        del app.dependency_overrides[get_generation_provider]


def test_generate_returns_503_when_all_providers_unavailable() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "carol@example.com")
    project_id = _create_project(client, token)

    app.dependency_overrides[get_generation_provider] = lambda: _FakeProvider(unavailable=True)
    try:
        response = client.post(
            f"/api/v1/projects/{project_id}/generate",
            json={"prompt": "say hi", "model": "mock-model"},
            headers=_auth_header(token),
        )
        assert response.status_code == 503
    finally:
        del app.dependency_overrides[get_generation_provider]


def test_stream_endpoint_reconstructs_full_content_and_persists() -> None:
    client, SessionLocal = build_test_client()
    token = _register_and_login(client, "dave@example.com")
    project_id = _create_project(client, token)

    app.dependency_overrides[get_generation_provider] = lambda: _FakeProvider(content="a longer streamed response")
    try:
        response = client.post(
            f"/api/v1/projects/{project_id}/generate/stream",
            json={"prompt": "say hi", "model": "mock-model"},
            headers=_auth_header(token),
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        chunks = []
        for line in response.text.splitlines():
            if not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload == "[DONE]":
                continue
            chunks.append(payload)

        assert "".join(chunks) == "a longer streamed response"

        db = SessionLocal()
        try:
            persisted = db.query(generation_models.GenerationResponse).first()
            assert persisted is not None
            assert persisted.content == "a longer streamed response"
        finally:
            db.close()
    finally:
        del app.dependency_overrides[get_generation_provider]
