from app.domains.auth import models as auth_models  # noqa: F401
from app.domains.auth.security import decode_token
from tests.utils import build_test_client


def _register(client, email="frank@example.com", password="hunter22"):
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    return resp.json()


def test_login_returns_access_and_refresh_tokens() -> None:
    client, _ = build_test_client()
    user = _register(client)

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "frank@example.com", "password": "hunter22"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]

    payload = decode_token(body["access_token"])
    assert payload["type"] == "access"
    assert payload["sub"] == user["id"]


def test_login_wrong_password_returns_401() -> None:
    client, _ = build_test_client()
    _register(client)

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "frank@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_login_unknown_user_returns_401() -> None:
    client, _ = build_test_client()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": "ghost@example.com", "password": "whatever1"},
    )
    assert response.status_code == 401
