import random
import time
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.domains.generation.models import GenerationRequest, GenerationResponse
from app.domains.generation.providers.base import GenerationError, Provider
from app.domains.generation.retry import call_with_retry


def execute_generation(
    db: Session,
    *,
    project_id: UUID,
    created_by: UUID,
    prompt: str,
    model: str,
    provider: Provider,
    max_attempts: int = 1,
    base_backoff_seconds: float = 0.1,
    max_backoff_seconds: float = 10.0,
    jitter: bool = True,
    sleep_fn: Callable[[float], None] = time.sleep,
    random_fn: Callable[[], float] = random.random,
) -> GenerationResponse:
    """Persist a GenerationRequest, call the provider (with retry), persist the result.

    TODO (you): implement this. See docs/stages/phase4-generation.md, Stage 5:
      1. Create a GenerationRequest with status="pending", commit it (so it
         has an id even if the call below fails).
      2. Call call_with_retry(...) with the given provider/retry params.
      3. On GenerationError: set status="failed", commit, re-raise.
      4. On success: create a GenerationResponse from the result, set
         status="succeeded", commit both, return the persisted GenerationResponse.
    """
    raise NotImplementedError
