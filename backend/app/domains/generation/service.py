import json
import logging
import random
import time
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.generation.cache import GenerationCache
from app.domains.generation.models import GenerationRequest, GenerationResponse
from app.domains.generation.providers.base import GenerationError, Provider
from app.domains.generation.retry import call_with_retry

logger = logging.getLogger(__name__)


def execute_generation(
    db: Session,
    *,
    project_id: UUID,
    created_by: UUID,
    prompt: str,
    model: str,
    provider: Provider,
    cache: GenerationCache | None = None,
    max_attempts: int = 1,
    base_backoff_seconds: float = 0.1,
    max_backoff_seconds: float = 10.0,
    jitter: bool = True,
    sleep_fn: Callable[[float], None] = time.sleep,
    random_fn: Callable[[], float] = random.random,
) -> GenerationResponse:
    request = GenerationRequest(
        project_id=project_id,
        model=model,
        status="pending",
        created_by=created_by,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    # A cache lookup/write failure (Redis down, network blip) must never
    # break generation itself — caching is an optimization, not a
    # correctness requirement, so any exception here just falls through to
    # a normal provider call.
    cache_key: str | None = None
    cached_payload: dict | None = None
    if cache is not None:
        try:
            cache_key = cache.build_key(prompt, model)
            cached_raw = cache.get(cache_key)
            cached_payload = json.loads(cached_raw) if cached_raw is not None else None
        except Exception as exc:
            logger.warning("cache lookup failed, proceeding without cache: %s", exc)

    if cached_payload is not None:
        response = GenerationResponse(
            request_id=request.id,
            provider=cached_payload["provider"],
            model=cached_payload["model"],
            content=cached_payload["content"],
            tokens_used=cached_payload["tokens_used"],
            latency_ms=cached_payload["latency_ms"],
        )
        request.status = "succeeded"
        db.add(response)
        db.add(request)
        db.commit()
        db.refresh(response)
        response.cache_hit = True
        return response

    try:
        result = call_with_retry(
            provider, prompt, model,
            max_attempts=max_attempts, base_backoff_seconds=base_backoff_seconds,
            max_backoff_seconds=max_backoff_seconds, jitter=jitter,
            sleep_fn=sleep_fn, random_fn=random_fn,
        )
    except GenerationError:
        request.status = "failed"
        db.add(request)
        db.commit()
        raise

    response = GenerationResponse(
        request_id=request.id,
        provider=result.provider,
        model=result.model,
        content=result.content,
        tokens_used=result.tokens_used,
        latency_ms=result.latency_ms,
    )
    request.status = "succeeded"
    db.add(response)
    db.add(request)
    db.commit()
    db.refresh(response)

    if cache is not None and cache_key is not None:
        try:
            cache.set(cache_key, json.dumps({
                "provider": result.provider,
                "model": result.model,
                "content": result.content,
                "tokens_used": result.tokens_used,
                "latency_ms": result.latency_ms,
            }))
        except Exception as exc:
            logger.warning("cache write failed: %s", exc)

    response.cache_hit = False
    return response
