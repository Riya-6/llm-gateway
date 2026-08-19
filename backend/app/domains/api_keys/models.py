from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ApiKey(Base):
      __tablename__ = "api_keys"
      id: Mapped[UUID]= mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
      project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
      name: Mapped[str]= mapped_column(String(255), nullable=False)
      key_prefix: Mapped[str]= mapped_column(String(255), nullable=False)
      key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)      # unique, indexed
      created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
      last_used_at: Mapped[datetime | None]= mapped_column(DateTime(timezone=True), nullable=True)
      revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  