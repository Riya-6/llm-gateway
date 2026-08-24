from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GenerateRequest(BaseModel):
    prompt: str
    model: str = "mock-model"


class GenerateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    provider: str
    model: str
    content: str
    tokens_used: int
    latency_ms: int
    created_at: datetime
    # Defaults False until the cache (Phase 5) is actually wired into the
    # generate() flow — safe with from_attributes even though the ORM
    # GenerationResponse has no matching column.
    cache_hit: bool = False
