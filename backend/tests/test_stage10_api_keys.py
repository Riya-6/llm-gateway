from app.domains.auth import models as auth_models  # noqa: F401
from app.domains.projects import models as project_models  # noqa: F401
from app.domains.api_keys import models as api_key_models  # noqa: F401
from tests.utils import build_test_client


def _register_and_login(client, email, password="hunter22"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return login.json()["access_token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _create_project(client, token, name="Gateway Prod"):
    resp = client.post("/api/v1/projects", json={"name": name}, headers=_auth_header(token))
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_api_key_returns_plaintext_once() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "jill@example.com")
    project_id = _create_project(client, token)

    response = client.post(
        f"/api/v1/projects/{project_id}/api-keys",
        json={"name": "ci key"},
        headers=_auth_header(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["api_key"].startswith("lgw_")
    assert body["key_prefix"] == body["api_key"][:12]


def test_list_api_keys_never_exposes_plaintext() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "kyle@example.com")
    project_id = _create_project(client, token)
    client.post(f"/api/v1/projects/{project_id}/api-keys", json={"name": "ci key"}, headers=_auth_header(token))

    listing = client.get(f"/api/v1/projects/{project_id}/api-keys", headers=_auth_header(token))
    assert listing.status_code == 200
    for key in listing.json():
        assert "api_key" not in key
        assert "key_hash" not in key


def test_verify_endpoint_accepts_valid_key() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "liam@example.com")
    project_id = _create_project(client, token)
    created = client.post(
        f"/api/v1/projects/{project_id}/api-keys", json={"name": "ci key"}, headers=_auth_header(token)
    ).json()

    response = client.get("/api/v1/api-keys/verify", headers={"X-API-Key": created["api_key"]})
    assert response.status_code == 200
    assert response.json()["project_id"] == project_id


def test_verify_endpoint_rejects_garbage_key() -> None:
    client, _ = build_test_client()
    response = client.get("/api/v1/api-keys/verify", headers={"X-API-Key": "lgw_not-a-real-key"})
    assert response.status_code == 401


def test_revoked_key_is_rejected() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "mia@example.com")
    project_id = _create_project(client, token)
    created = client.post(
        f"/api/v1/projects/{project_id}/api-keys", json={"name": "ci key"}, headers=_auth_header(token)
    ).json()

    revoke = client.delete(
        f"/api/v1/projects/{project_id}/api-keys/{created['id']}", headers=_auth_header(token)
    )
    assert revoke.status_code == 204

    response = client.get("/api/v1/api-keys/verify", headers={"X-API-Key": created["api_key"]})
    assert response.status_code == 401


def test_non_owner_cannot_manage_project_keys() -> None:
    client, _ = build_test_client()
    owner_token = _register_and_login(client, "nina@example.com")
    other_token = _register_and_login(client, "oscar@example.com")
    project_id = _create_project(client, owner_token)

    create_as_other = client.post(
        f"/api/v1/projects/{project_id}/api-keys", json={"name": "sneaky"}, headers=_auth_header(other_token)
    )
    assert create_as_other.status_code == 404

    list_as_other = client.get(f"/api/v1/projects/{project_id}/api-keys", headers=_auth_header(other_token))
    assert list_as_other.status_code == 404
