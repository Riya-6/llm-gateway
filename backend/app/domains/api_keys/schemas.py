from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApiKeyCreate(BaseModel):
    name: str
class ApiKeyCreated(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    api_key: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None