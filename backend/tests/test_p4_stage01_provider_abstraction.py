import httpx
import pytest
from fastapi.testclient import TestClient

from app.domains.generation.providers.anthropic_provider import AnthropicProvider
from app.domains.generation.providers.base import GenerationError, ProviderTimeoutError
from app.domains.generation.providers.mock_http_provider import MockHTTPProvider
from app.domains.generation.providers.ollama_provider import OllamaProvider
from app.domains.generation.providers.openai_provider import OpenAIProvider
from app.domains.generation.providers.pricing import estimated_cost_per_1k_tokens
from app.domains.generation.providers.scoring import ProviderStats
from app.mock_provider.server import app as mock_server_app


class FakeResponse:
    def __init__(self, status_code: int, json_body: dict, text: str = "") -> None:
        self.status_code = status_code
        self._json_body = json_body
        self.text = text or str(json_body)

    def json(self) -> dict:
        return self._json_body


def _fake_post(url, **kwargs):
    if "openai.com" in url:
        return FakeResponse(
            200,
            {"choices": [{"message": {"content": "hi from openai"}}], "usage": {"total_tokens": 7}},
        )
    if "anthropic.com" in url:
        return FakeResponse(
            200,
            {"content": [{"text": "hi from anthropic"}], "usage": {"input_tokens": 3, "output_tokens": 4}},
        )
    if "11434" in url:
        return FakeResponse(200, {"response": "hi from ollama", "prompt_eval_count": 2, "eval_count": 3})
    return FakeResponse(200, {"content": "hi from mock", "tokens_used": 5})


@pytest.mark.parametrize(
    "provider_factory",
    [
        lambda: OpenAIProvider(api_key="sk-test"),
        lambda: AnthropicProvider(api_key="sk-test"),
        lambda: MockHTTPProvider(base_url="http://localhost:9100"),
        lambda: OllamaProvider(base_url="http://localhost:11434"),
    ],
)
def test_all_providers_satisfy_the_same_interface(monkeypatch, provider_factory) -> None:
    monkeypatch.setattr(httpx, "post", _fake_post)

    provider = provider_factory()
    result = provider.generate("say hi", "some-model")

    assert result.provider == provider.name
    assert result.model == "some-model"
    assert isinstance(result.content, str) and result.content
    assert isinstance(result.tokens_used, int)
    assert isinstance(result.latency_ms, int)


def test_openai_provider_raises_on_http_error(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "post", lambda url, **kw: FakeResponse(500, {}, text="server error"))

    provider = OpenAIProvider(api_key="sk-test")
    with pytest.raises(GenerationError):
        provider.generate("say hi", "some-model")


def test_mock_provider_raises_provider_timeout_on_httpx_timeout(monkeypatch) -> None:
    def _raise_timeout(url, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", _raise_timeout)

    provider = MockHTTPProvider(base_url="http://localhost:9100")
    with pytest.raises(ProviderTimeoutError):
        provider.generate("say hi", "some-model")


def test_mock_server_normal_mode_succeeds() -> None:
    client = TestClient(mock_server_app)
    client.post("/admin/reset")

    response = client.post("/v1/generate", json={"model": "mock-model", "prompt": "hello there"})

    assert response.status_code == 200
    body = response.json()
    assert "content" in body
    assert body["tokens_used"] >= 1


def test_mock_server_error_mode_returns_500() -> None:
    client = TestClient(mock_server_app)
    client.post("/admin/mode", json={"mode": "error"})

    response = client.post("/v1/generate", json={"model": "mock-model", "prompt": "hello"})

    assert response.status_code == 500
    client.post("/admin/reset")


def test_mock_server_flaky_mode_deterministic_at_extremes() -> None:
    client = TestClient(mock_server_app)

    client.post("/admin/mode", json={"mode": "flaky", "flaky_failure_rate": 1.0})
    always_fails = client.post("/v1/generate", json={"model": "mock-model", "prompt": "hello"})
    assert always_fails.status_code == 503

    client.post("/admin/mode", json={"mode": "flaky", "flaky_failure_rate": 0.0})
    always_succeeds = client.post("/v1/generate", json={"model": "mock-model", "prompt": "hello"})
    assert always_succeeds.status_code == 200

    client.post("/admin/reset")


def test_mock_server_admin_mode_round_trips() -> None:
    client = TestClient(mock_server_app)

    client.post("/admin/mode", json={"mode": "timeout"})
    state = client.get("/admin/mode").json()
    assert state["mode"] == "timeout"

    client.post("/admin/reset")
    reset_state = client.get("/admin/mode").json()
    assert reset_state["mode"] == "normal"
    assert reset_state["call_count"] == 0


def test_pricing_table_covers_every_provider() -> None:
    for provider_name in ("openai", "anthropic", "ollama", "mock"):
        assert estimated_cost_per_1k_tokens(provider_name) >= 0.0

    assert estimated_cost_per_1k_tokens("ollama") == 0.0
    assert estimated_cost_per_1k_tokens("unknown-provider") == 0.0


def test_provider_stats_shape_matches_scoring_interface() -> None:
    stats = ProviderStats(provider_name="ollama", recent_latency_ms=120.0, cost_per_1k_tokens=0.0)

    assert stats.provider_name == "ollama"
    assert stats.recent_latency_ms == 120.0
    assert stats.cost_per_1k_tokens == 0.0
