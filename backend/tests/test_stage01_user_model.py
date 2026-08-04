import pytest
from sqlalchemy.exc import IntegrityError

from app.domains.auth import models as auth_models  # noqa: F401  (registers User on Base.metadata)
from tests.utils import build_test_client


def test_create_and_read_user() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user = auth_models.User(
            email="alice@example.com",
            hashed_password="not-a-real-hash",
            full_name="Alice",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.is_active is True
        assert user.created_at is not None

        fetched = (
            db.query(auth_models.User)
            .filter(auth_models.User.email == "alice@example.com")
            .one()
        )
        assert fetched.id == user.id
        assert fetched.full_name == "Alice"
    finally:
        db.close()


def test_duplicate_email_rejected() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        db.add(auth_models.User(email="bob@example.com", hashed_password="x"))
        db.commit()

        db.add(auth_models.User(email="bob@example.com", hashed_password="y"))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()
