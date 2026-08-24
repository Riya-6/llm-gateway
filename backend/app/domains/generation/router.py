import logging
from collections.abc import Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.generation.circuit_breaker import CircuitBreaker
from app.domains.generation.models import GenerationResponse
from app.domains.generation.provider_router import AllProvidersUnavailableError, ProviderRoute, ProviderRouter
from app.domains.generation.providers.anthropic_provider import AnthropicProvider
from app.domains.generation.providers.base import GenerationError, Provider
from app.domains.generation.providers.mock_http_provider import MockHTTPProvider
from app.domains.generation.providers.ollama_provider import OllamaProvider
from app.domains.generation.providers.openai_provider import OpenAIProvider
from app.domains.generation.schemas import GenerateRequest, GenerateResponse
from app.domains.generation.service import execute_generation
from app.domains.projects.models import Project

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_circuit_breaker() -> CircuitBreaker:
    # Configurable via CIRCUIT_BREAKER_FAILURE_THRESHOLD / _RECOVERY_TIMEOUT_SECONDS
    # rather than hardcoded, so scripts/compare_thresholds.py (stage 10) can
    # drive the same chaos scenario against two different configs without
    # editing code between runs.
    return CircuitBreaker(
        failure_threshold=settings.circuit_breaker_failure_threshold,
        recovery_timeout_seconds=settings.circuit_breaker_recovery_timeout_seconds,
    )


def _build_real_provider(name: str) -> Provider:
    if name == "openai":
        return OpenAIProvider(api_key=settings.openai_api_key or "")
    if name == "anthropic":
        return AnthropicProvider(api_key=settings.anthropic_api_key or "")
    if name == "ollama":
        return OllamaProvider()
    raise ValueError(f"unknown generation_real_fallback_provider: {name!r} (expected openai/anthropic/ollama)")


def _build_default_routes() -> list[ProviderRoute]:
    # GENERATION_MOCK_ONLY=true skips OpenAI/Anthropic/Ollama entirely, so
    # chaos testing (backend/scripts/chaos_test.py) exercises retry/circuit-
    # breaker/fallback logic against a fast, controllable target instead of
    # burning real (slow, always-failing-without-keys) network round trips
    # on every single request — real provider latency was drowning out the
    # actual chaos-test signal (see docs/decisions.md).
    if settings.generation_mock_only:
        if settings.generation_real_fallback_provider:
            # Mock stays the (admin-toggleable) primary; the fallback route
            # is exactly one real provider, chosen by name, so a fallback
            # test can use real hosted latency/behavior on the fallback leg
            # without pulling in every provider (and their API costs) at once.
            return [
                ProviderRoute(
                    provider=MockHTTPProvider(base_url=settings.mock_provider_url, name="mock-primary"),
                    breaker=_build_circuit_breaker(),
                ),
                ProviderRoute(provider=_build_real_provider(settings.generation_real_fallback_provider), breaker=_build_circuit_breaker()),
            ]
        if settings.mock_fallback_provider_url:
            # Two-mock-provider chaos-test config: a second mock instance
            # (kept in "normal" mode) stands in as a real fallback target,
            # so a chaos run can prove actual handoff — not just that the
            # circuit breaker opened — without spending on real providers.
            return [
                ProviderRoute(
                    provider=MockHTTPProvider(base_url=settings.mock_provider_url, name="mock-primary"),
                    breaker=_build_circuit_breaker(),
                ),
                ProviderRoute(
                    provider=MockHTTPProvider(base_url=settings.mock_fallback_provider_url, name="mock-fallback"),
                    breaker=_build_circuit_breaker(),
                ),
            ]
        return [ProviderRoute(provider=MockHTTPProvider(base_url=settings.mock_provider_url), breaker=_build_circuit_breaker())]

    # Default provider list, in priority order: real hosted providers first,
    # then local Ollama, then the controllable mock as a last resort. Each
    # gets its own CircuitBreaker (stage 4) so one provider tripping doesn't
    # affect the others. Missing API keys/an unreachable Ollama just mean
    # that route fails and gets skipped by the fallback logic (stage 6) —
    # not a startup error.
    return [
        ProviderRoute(provider=OpenAIProvider(api_key=settings.openai_api_key or ""), breaker=_build_circuit_breaker()),
        ProviderRoute(provider=AnthropicProvider(api_key=settings.anthropic_api_key or ""), breaker=_build_circuit_breaker()),
        ProviderRoute(provider=OllamaProvider(), breaker=_build_circuit_breaker()),
        ProviderRoute(provider=MockHTTPProvider(base_url=settings.mock_provider_url), breaker=_build_circuit_breaker()),
    ]


_default_router = ProviderRouter(_build_default_routes())


def get_generation_provider() -> Provider:
    return _default_router


def _get_owned_project(project_id: UUID, current_user: User, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _chunk_content(content: str, chunk_size: int = 20) -> Iterator[str]:
    for i in range(0, len(content), chunk_size):
        yield content[i : i + chunk_size]


@router.post("/projects/{project_id}/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
def generate(
    project_id: UUID,
    payload: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: Provider = Depends(get_generation_provider),
) -> GenerationResponse:
    _get_owned_project(project_id, current_user, db)
    try:
        return execute_generation(
            db,
            project_id=project_id,
            created_by=current_user.id,
            prompt=payload.prompt,
            model=payload.model,
            provider=provider,
        )
    except AllProvidersUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No provider currently available"
        )
    except GenerationError as exc:
        logger.warning("generation provider failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Generation provider failed")


@router.post("/projects/{project_id}/generate/stream")
def generate_stream(
    project_id: UUID,
    payload: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: Provider = Depends(get_generation_provider),
) -> StreamingResponse:
    _get_owned_project(project_id, current_user, db)
    try:
        response = execute_generation(
            db,
            project_id=project_id,
            created_by=current_user.id,
            prompt=payload.prompt,
            model=payload.model,
            provider=provider,
        )
    except AllProvidersUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No provider currently available"
        )
    except GenerationError as exc:
        logger.warning("generation provider failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Generation provider failed")

    def event_stream() -> Iterator[str]:
        for chunk in _chunk_content(response.content):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
