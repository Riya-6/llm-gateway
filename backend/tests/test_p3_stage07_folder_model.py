import pytest
from sqlalchemy.exc import IntegrityError

from app.domains.auth import models as auth_models  # noqa: F401
from app.domains.projects import models as project_models
from app.domains.prompts import models as prompt_models
from tests.utils import build_test_client


def _make_user_and_project(db):
    user = auth_models.User(email="owner@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    project = project_models.Project(name="Proj A", owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return user, project


def test_create_folder_and_assign_prompt_to_it() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)

        folder = prompt_models.Folder(project_id=project.id, name="Marketing")
        db.add(folder)
        db.commit()
        db.refresh(folder)

        prompt = prompt_models.Prompt(
            project_id=project.id, name="Greeting", created_by=user.id, folder_id=folder.id
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        assert prompt.folder_id == folder.id
    finally:
        db.close()


def test_duplicate_folder_name_within_project_rejected() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        _, project = _make_user_and_project(db)

        db.add(prompt_models.Folder(project_id=project.id, name="Marketing"))
        db.commit()

        db.add(prompt_models.Folder(project_id=project.id, name="Marketing"))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_deleting_folder_sets_prompt_folder_id_to_null_not_deleting_prompt() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)

        folder = prompt_models.Folder(project_id=project.id, name="Marketing")
        db.add(folder)
        db.commit()
        db.refresh(folder)

        prompt = prompt_models.Prompt(
            project_id=project.id, name="Greeting", created_by=user.id, folder_id=folder.id
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        db.delete(folder)
        db.commit()

        db.refresh(prompt)
        assert db.get(prompt_models.Prompt, prompt.id) is not None
        assert prompt.folder_id is None
    finally:
        db.close()
