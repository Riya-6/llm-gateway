import pytest
from sqlalchemy.exc import IntegrityError

from app.domains.auth import models as auth_models  # noqa: F401
from app.domains.projects import models as project_models
from app.domains.prompts import models as prompt_models
from tests.utils import build_test_client


def _make_user_project_prompt(db):
    user = auth_models.User(email="owner@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    project = project_models.Project(name="Proj A", owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)

    prompt = prompt_models.Prompt(project_id=project.id, name="Greeting", created_by=user.id)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return user, project, prompt


def test_create_versions_with_sequential_numbers() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, _, prompt = _make_user_project_prompt(db)

        v1 = prompt_models.PromptVersion(
            prompt_id=prompt.id, version_number=1, content="Hello", created_by=user.id
        )
        v2 = prompt_models.PromptVersion(
            prompt_id=prompt.id, version_number=2, content="Hello there", created_by=user.id
        )
        db.add_all([v1, v2])
        db.commit()

        versions = (
            db.query(prompt_models.PromptVersion)
            .filter(prompt_models.PromptVersion.prompt_id == prompt.id)
            .order_by(prompt_models.PromptVersion.version_number)
            .all()
        )
        assert [v.version_number for v in versions] == [1, 2]
    finally:
        db.close()


def test_duplicate_version_number_for_same_prompt_rejected() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, _, prompt = _make_user_project_prompt(db)

        db.add(prompt_models.PromptVersion(prompt_id=prompt.id, version_number=1, content="A", created_by=user.id))
        db.commit()

        db.add(prompt_models.PromptVersion(prompt_id=prompt.id, version_number=1, content="B", created_by=user.id))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_deleting_prompt_cascades_to_its_versions() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, _, prompt = _make_user_project_prompt(db)
        db.add(prompt_models.PromptVersion(prompt_id=prompt.id, version_number=1, content="A", created_by=user.id))
        db.commit()

        db.delete(prompt)
        db.commit()

        remaining = (
            db.query(prompt_models.PromptVersion)
            .filter(prompt_models.PromptVersion.prompt_id == prompt.id)
            .all()
        )
        assert remaining == []
    finally:
        db.close()
