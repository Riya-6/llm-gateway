from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.projects.models import Project
from app.domains.projects.schemas import ProjectCreate, ProjectRead

router = APIRouter()

@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = Project(name=payload.name, owner_id=current_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Project]:
    return db.query(Project).filter(Project.owner_id == current_user.id).all()


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project
