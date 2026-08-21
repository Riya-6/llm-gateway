from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class Prompt(Base):
    __tablename__ = "prompts"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_prompts_project_id_name"),)

    id: Mapped[UUID]=mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)            # primary key, default=uuid4
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)    # FK -> projects.id, not null, indexed
    name: Mapped[str] = mapped_column(String(255), nullable=False)           # not null
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)    # FK -> users.id, not null
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    folder_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("folders.id", ondelete="SET NULL"), nullable=True, index=True
    )

class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_id", "version_number", name="uq_prompt_versions_prompt_id_version_number"),)

    id: Mapped[UUID]=mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4) 
    prompt_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    created_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_tags_project_id_name"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PromptTag(Base):
    __tablename__ = "prompt_tags"

    prompt_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("prompts.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )


class Folder(Base):
    __tablename__ = "folders"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_folders_project_id_name"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())