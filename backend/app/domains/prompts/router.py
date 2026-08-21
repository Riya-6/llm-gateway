from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.projects.models import Project
from app.domains.prompts.models import Folder, Prompt, PromptTag, PromptVersion, Tag
from app.domains.prompts.schemas import (
    FolderCreate,
    FolderRead,
    PromptCreate,
    PromptRead,
    PromptUpdate,
    PromptVersionCreate,
    PromptVersionRead,
    TagCreate,
    TagRead,
)

router = APIRouter()


def _get_owned_project(project_id: UUID, current_user: User, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _get_project_prompt(project_id: UUID, prompt_id: UUID, db: Session) -> Prompt:
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id, Prompt.project_id == project_id).first()
    if prompt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
    return prompt


@router.post("/projects/{project_id}/prompts", response_model=PromptRead, status_code=status.HTTP_201_CREATED)
def create_prompt(
    project_id: UUID,
    payload: PromptCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Prompt:
    _get_owned_project(project_id, current_user, db)

    existing = db.query(Prompt).filter(Prompt.project_id == project_id, Prompt.name == payload.name).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Prompt name already exists in this project")

    prompt = Prompt(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        created_by=current_user.id,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.get("/projects/{project_id}/prompts", response_model=list[PromptRead])
def list_prompts(
    project_id: UUID,
    search: str | None = None,
    tag: str | None = None,
    folder_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Prompt]:
    _get_owned_project(project_id, current_user, db)

    query = db.query(Prompt).filter(Prompt.project_id == project_id)

    if search is not None:
        query = query.filter(
            or_(Prompt.name.ilike(f"%{search}%"), Prompt.description.ilike(f"%{search}%"))
        )

    if tag is not None:
        query = query.join(PromptTag, PromptTag.prompt_id == Prompt.id).join(
            Tag, Tag.id == PromptTag.tag_id
        ).filter(Tag.name == tag)

    if folder_id is not None:
        query = query.filter(Prompt.folder_id == folder_id)

    return query.all()


@router.get("/projects/{project_id}/prompts/{prompt_id}", response_model=PromptRead)
def get_prompt(
    project_id: UUID,
    prompt_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Prompt:
    _get_owned_project(project_id, current_user, db)
    return _get_project_prompt(project_id, prompt_id, db)


@router.patch("/projects/{project_id}/prompts/{prompt_id}", response_model=PromptRead)
def update_prompt(
    project_id: UUID,
    prompt_id: UUID,
    payload: PromptUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Prompt:
    _get_owned_project(project_id, current_user, db)
    prompt = _get_project_prompt(project_id, prompt_id, db)

    updates = payload.model_dump(exclude_unset=True)
    if "folder_id" in updates and updates["folder_id"] is not None:
        folder = (
            db.query(Folder)
            .filter(Folder.id == updates["folder_id"], Folder.project_id == project_id)
            .first()
        )
        if folder is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    for field, value in updates.items():
        setattr(prompt, field, value)

    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.delete("/projects/{project_id}/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt(
    project_id: UUID,
    prompt_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_project(project_id, current_user, db)
    prompt = _get_project_prompt(project_id, prompt_id, db)
    db.delete(prompt)
    db.commit()


@router.post(
    "/projects/{project_id}/prompts/{prompt_id}/versions",
    response_model=PromptVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt_version(
    project_id: UUID,
    prompt_id: UUID,
    payload: PromptVersionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PromptVersion:
    _get_owned_project(project_id, current_user, db)
    _get_project_prompt(project_id, prompt_id, db)

    last_version_number = (
        db.query(PromptVersion.version_number)
        .filter(PromptVersion.prompt_id == prompt_id)
        .order_by(PromptVersion.version_number.desc())
        .limit(1)
        .scalar()
    )
    next_version_number = (last_version_number or 0) + 1

    version = PromptVersion(
        prompt_id=prompt_id,
        version_number=next_version_number,
        content=payload.content,
        created_by=current_user.id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@router.get(
    "/projects/{project_id}/prompts/{prompt_id}/versions",
    response_model=list[PromptVersionRead],
)
def list_prompt_versions(
    project_id: UUID,
    prompt_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PromptVersion]:
    _get_owned_project(project_id, current_user, db)
    _get_project_prompt(project_id, prompt_id, db)
    return (
        db.query(PromptVersion)
        .filter(PromptVersion.prompt_id == prompt_id)
        .order_by(PromptVersion.version_number.asc())
        .all()
    )


@router.get(
    "/projects/{project_id}/prompts/{prompt_id}/versions/latest",
    response_model=PromptVersionRead,
)
def get_latest_prompt_version(
    project_id: UUID,
    prompt_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PromptVersion:
    _get_owned_project(project_id, current_user, db)
    _get_project_prompt(project_id, prompt_id, db)

    version = (
        db.query(PromptVersion)
        .filter(PromptVersion.prompt_id == prompt_id)
        .order_by(PromptVersion.version_number.desc())
        .first()
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No versions for this prompt")
    return version


@router.get(
    "/projects/{project_id}/prompts/{prompt_id}/versions/{version_number}",
    response_model=PromptVersionRead,
)
def get_prompt_version(
    project_id: UUID,
    prompt_id: UUID,
    version_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PromptVersion:
    _get_owned_project(project_id, current_user, db)
    _get_project_prompt(project_id, prompt_id, db)

    version = (
        db.query(PromptVersion)
        .filter(PromptVersion.prompt_id == prompt_id, PromptVersion.version_number == version_number)
        .first()
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return version


@router.post("/projects/{project_id}/tags", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(
    project_id: UUID,
    payload: TagCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Tag:
    _get_owned_project(project_id, current_user, db)

    existing = db.query(Tag).filter(Tag.project_id == project_id, Tag.name == payload.name).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag name already exists in this project")

    tag = Tag(project_id=project_id, name=payload.name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.get("/projects/{project_id}/tags", response_model=list[TagRead])
def list_tags(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Tag]:
    _get_owned_project(project_id, current_user, db)
    return db.query(Tag).filter(Tag.project_id == project_id).all()


@router.post(
    "/projects/{project_id}/prompts/{prompt_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def attach_tag_to_prompt(
    project_id: UUID,
    prompt_id: UUID,
    tag_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_project(project_id, current_user, db)
    _get_project_prompt(project_id, prompt_id, db)

    existing = (
        db.query(PromptTag)
        .filter(PromptTag.prompt_id == prompt_id, PromptTag.tag_id == tag_id)
        .first()
    )
    if existing is None:
        db.add(PromptTag(prompt_id=prompt_id, tag_id=tag_id))
        db.commit()


@router.delete(
    "/projects/{project_id}/prompts/{prompt_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def detach_tag_from_prompt(
    project_id: UUID,
    prompt_id: UUID,
    tag_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _get_owned_project(project_id, current_user, db)
    _get_project_prompt(project_id, prompt_id, db)

    existing = (
        db.query(PromptTag)
        .filter(PromptTag.prompt_id == prompt_id, PromptTag.tag_id == tag_id)
        .first()
    )
    if existing is not None:
        db.delete(existing)
        db.commit()


@router.get(
    "/projects/{project_id}/prompts/{prompt_id}/tags",
    response_model=list[TagRead],
)
def list_prompt_tags(
    project_id: UUID,
    prompt_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Tag]:
    _get_owned_project(project_id, current_user, db)
    _get_project_prompt(project_id, prompt_id, db)
    return (
        db.query(Tag)
        .join(PromptTag, PromptTag.tag_id == Tag.id)
        .filter(PromptTag.prompt_id == prompt_id)
        .all()
    )


def _get_project_folder(project_id: UUID, folder_id: UUID, db: Session) -> Folder:
    folder = db.query(Folder).filter(Folder.id == folder_id, Folder.project_id == project_id).first()
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    return folder


@router.post("/projects/{project_id}/folders", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
def create_folder(
    project_id: UUID,
    payload: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Folder:
    _get_owned_project(project_id, current_user, db)

    existing = db.query(Folder).filter(Folder.project_id == project_id, Folder.name == payload.name).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Folder name already exists in this project")

    folder = Folder(project_id=project_id, name=payload.name)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


@router.get("/projects/{project_id}/folders", response_model=list[FolderRead])
def list_folders(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Folder]:
    _get_owned_project(project_id, current_user, db)
    return db.query(Folder).filter(Folder.project_id == project_id).all()


@router.get("/projects/{project_id}/folders/{folder_id}/prompts", response_model=list[PromptRead])
def list_folder_prompts(
    project_id: UUID,
    folder_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Prompt]:
    _get_owned_project(project_id, current_user, db)
    _get_project_folder(project_id, folder_id, db)
    return db.query(Prompt).filter(Prompt.project_id == project_id, Prompt.folder_id == folder_id).all()
