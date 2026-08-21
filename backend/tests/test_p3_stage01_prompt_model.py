import pytest
from sqlalchemy.exc import IntegrityError

from app.domains.auth import models as auth_models  # noqa: F401
from app.domains.projects import models as project_models
from app.domains.prompts import models as prompt_models  # noqa: F401
from tests.utils import build_test_client


def _make_user_and_project(db, email="owner@example.com", project_name="Proj A"):
    user = auth_models.User(email=email, hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    project = project_models.Project(name=project_name, owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return user, project


def test_create_and_read_prompt() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)

        prompt = prompt_models.Prompt(
            project_id=project.id,
            name="Greeting",
            description="Says hello",
            created_by=user.id,
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        assert prompt.id is not None
        assert prompt.created_at is not None

        fetched = db.query(prompt_models.Prompt).filter(prompt_models.Prompt.name == "Greeting").one()
        assert fetched.id == prompt.id
    finally:
        db.close()


def test_duplicate_name_within_same_project_rejected() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)

        db.add(prompt_models.Prompt(project_id=project.id, name="Greeting", created_by=user.id))
        db.commit()

        db.add(prompt_models.Prompt(project_id=project.id, name="Greeting", created_by=user.id))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_same_name_allowed_in_different_projects() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project_a = _make_user_and_project(db, project_name="Proj A")
        _, project_b = _make_user_and_project(db, email="owner2@example.com", project_name="Proj B")

        db.add(prompt_models.Prompt(project_id=project_a.id, name="Greeting", created_by=user.id))
        db.add(prompt_models.Prompt(project_id=project_b.id, name="Greeting", created_by=user.id))
        db.commit()  # should not raise
    finally:
        db.close()
