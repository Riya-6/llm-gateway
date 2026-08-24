from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class GenerationRequest(Base):
    __tablename__ = "generation_requests"

    id: Mapped[UUID]=mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    prompt_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("prompts.id"), nullable=True, index=True)  
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(255), nullable=False, default="pending")      
    created_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class GenerationResponse(Base):
    __tablename__ = "generation_responses"

    id: Mapped[UUID]=mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("generation_requests.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())