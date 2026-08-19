from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str

class ProjectRead(BaseModel):
      id: UUID
      owner_id: UUID
      name: str
      created_at: datetime
      model_config = ConfigDict(from_attributes=True)