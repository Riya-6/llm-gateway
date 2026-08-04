from datetime import datetime, timedelta, timezone

from app.domains.auth import models as auth_models  # noqa: F401
from tests.utils import build_test_client


def _register_and_login(client, email="hank@example.com", password="hunter22"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return login.json()


def test_refresh_rotates_tokens() -> None:
    client, _ = build_test_client()
    original = _register_and_login(client)

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]})
    assert response.status_code == 200
    rotated = response.json()

    assert rotated["access_token"] != original["access_token"]
    assert rotated["refresh_token"] != original["refresh_token"]


def test_reusing_a_rotated_refresh_token_returns_401() -> None:
    client, _ = build_test_client()
    original = _register_and_login(client)

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]})
    assert first.status_code == 200

    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]})
    assert reuse.status_code == 401


def test_new_refresh_token_still_works() -> None:
    client, _ = build_test_client()
    original = _register_and_login(client)

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": original["refresh_token"]})
    rotated = first.json()

    second = client.post("/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert second.status_code == 200


def test_garbage_refresh_token_returns_401() -> None:
    client, _ = build_test_client()
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 401


def test_expired_refresh_token_row_returns_401() -> None:
    client, SessionLocal = build_test_client()
    tokens = _register_and_login(client)

    db = SessionLocal()
    try:
        row = db.query(auth_models.RefreshToken).order_by(auth_models.RefreshToken.created_at.desc()).first()
        assert row is not None, "login must persist a RefreshToken row"
        row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.add(row)
        db.commit()
    finally:
        db.close()

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 401
