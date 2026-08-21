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


def test_create_tag_and_attach_to_prompt() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        _, project, prompt = _make_user_project_prompt(db)

        tag = prompt_models.Tag(project_id=project.id, name="marketing")
        db.add(tag)
        db.commit()
        db.refresh(tag)

        db.add(prompt_models.PromptTag(prompt_id=prompt.id, tag_id=tag.id))
        db.commit()

        link = (
            db.query(prompt_models.PromptTag)
            .filter(prompt_models.PromptTag.prompt_id == prompt.id, prompt_models.PromptTag.tag_id == tag.id)
            .first()
        )
        assert link is not None
    finally:
        db.close()


def test_duplicate_tag_name_within_project_rejected() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        _, project, _ = _make_user_project_prompt(db)

        db.add(prompt_models.Tag(project_id=project.id, name="marketing"))
        db.commit()

        db.add(prompt_models.Tag(project_id=project.id, name="marketing"))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_attaching_same_tag_twice_rejected() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        _, project, prompt = _make_user_project_prompt(db)

        tag = prompt_models.Tag(project_id=project.id, name="marketing")
        db.add(tag)
        db.commit()
        db.refresh(tag)

        db.add(prompt_models.PromptTag(prompt_id=prompt.id, tag_id=tag.id))
        db.commit()

        db.add(prompt_models.PromptTag(prompt_id=prompt.id, tag_id=tag.id))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_deleting_prompt_cascades_to_tag_links() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        _, project, prompt = _make_user_project_prompt(db)

        tag = prompt_models.Tag(project_id=project.id, name="marketing")
        db.add(tag)
        db.commit()
        db.refresh(tag)

        db.add(prompt_models.PromptTag(prompt_id=prompt.id, tag_id=tag.id))
        db.commit()

        db.delete(prompt)
        db.commit()

        remaining = db.query(prompt_models.PromptTag).filter(prompt_models.PromptTag.tag_id == tag.id).all()
        assert remaining == []
        # the Tag itself should still exist — only the link was cascade-deleted
        assert db.get(prompt_models.Tag, tag.id) is not None
    finally:
        db.close()
