from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domains.api_keys.dependencies import get_current_project
from app.domains.api_keys.models import ApiKey
from app.domains.api_keys.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.domains.api_keys.security import generate_api_key
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.projects.models import Project

router = APIRouter()


def _get_owned_project(project_id: UUID, current_user: User, db: Session) -> Project:
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.owner_id == current_user.id)
        .first()
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post(
    "/projects/{project_id}/api-keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_api_key(
    project_id: UUID,
    payload: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyCreated:
    _get_owned_project(project_id, current_user, db)

    full_key, key_prefix, key_hash = generate_api_key()
    api_key = ApiKey(project_id=project_id, name=payload.name, key_prefix=key_prefix, key_hash=key_hash)
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return ApiKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        api_key=full_key,
        created_at=api_key.created_at,
    )


@router.get("/projects/{project_id}/api-keys", response_model=list[ApiKeyRead])
def list_api_keys(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApiKey]:
    _get_owned_project(project_id, current_user, db)
    return db.query(ApiKey).filter(ApiKey.project_id == project_id).all()


@router.delete("/projects/{project_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    project_id: UUID,
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_project(project_id, current_user, db)

    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.id == key_id, ApiKey.project_id == project_id)
        .first()
    )
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    api_key.revoked_at = datetime.now(timezone.utc)
    db.add(api_key)
    db.commit()


@router.get("/api-keys/verify")
def verify_api_key(project: Project = Depends(get_current_project)) -> dict:
    return {"project_id": str(project.id), "project_name": project.name}
