from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domains.api_keys.models import ApiKey
from app.domains.api_keys.security import hash_api_key
from app.domains.projects.models import Project


def get_current_project(
    api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Project:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    key_hash = hash_api_key(api_key)
    stored = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
        .first()
    )
    if stored is None:
        raise unauthorized

    project = db.get(Project, stored.project_id)
    if project is None:
        raise unauthorized

    stored.last_used_at = datetime.now(timezone.utc)
    db.add(stored)
    db.commit()

    return project
