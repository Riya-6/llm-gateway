from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PromptCreate(BaseModel):
    name: str
    description: str | None = None
class PromptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    
class PromptUpdate(BaseModel):
    name: str | None = None
    description: str | None = None