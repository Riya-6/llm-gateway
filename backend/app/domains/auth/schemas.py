from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field
# Defines 2 data contracts for user creation and reading.
# They ensure the shape of incoming and outgoing user data is consistent.
class UserCreate(BaseModel):
      email: EmailStr
      password: str = Field(min_length=8, max_length=128)
      full_name: str | None = None
class UserRead(BaseModel):
      id: UUID
      email: EmailStr
      full_name: str | None
      is_active: bool
      created_at: datetime
      model_config = ConfigDict(from_attributes=True) #sets the model to read data from Object Relational models (SQLAlchemy) instead of dictionaries.

# Defines a data contract for successful login.
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
