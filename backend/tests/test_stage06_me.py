from app.domains.auth import models as auth_models  # noqa: F401
from tests.utils import build_test_client


def _register_and_login(client, email="grace@example.com", password="hunter22"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return login.json()


def test_me_without_token_returns_401() -> None:
    client, _ = build_test_client()
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_valid_access_token_returns_current_user() -> None:
    client, _ = build_test_client()
    tokens = _register_and_login(client)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "grace@example.com"


def test_me_with_refresh_token_as_bearer_returns_401() -> None:
    client, _ = build_test_client()
    tokens = _register_and_login(client)

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert response.status_code == 401


def test_me_with_garbage_token_returns_401() -> None:
    client, _ = build_test_client()
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert response.status_code == 401
