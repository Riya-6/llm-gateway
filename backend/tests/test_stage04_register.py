from app.domains.auth import models as auth_models  # noqa: F401
from tests.utils import build_test_client


def test_register_returns_201_with_no_password_fields() -> None:
    client, _ = build_test_client()
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "carol@example.com", "password": "hunter22", "full_name": "Carol"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "carol@example.com"
    assert body["full_name"] == "Carol"
    assert "id" in body
    assert "password" not in body
    assert "hashed_password" not in body


def test_duplicate_email_returns_409() -> None:
    client, _ = build_test_client()
    payload = {"email": "dave@example.com", "password": "hunter22"}
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert "detail" in second.json()


def test_invalid_email_returns_422() -> None:
    client, _ = build_test_client()
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "hunter22"},
    )
    assert response.status_code == 422


def test_short_password_returns_422() -> None:
    client, _ = build_test_client()
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "erin@example.com", "password": "short"},
    )
    assert response.status_code == 422
