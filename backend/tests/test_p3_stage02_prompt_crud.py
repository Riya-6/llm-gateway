from app.domains.auth import models as auth_models  # noqa: F401
from app.domains.projects import models as project_models  # noqa: F401
from app.domains.prompts import models as prompt_models  # noqa: F401
from tests.utils import build_test_client


def _register_and_login(client, email, password="hunter22"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return login.json()["access_token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _create_project(client, token, name="Proj A"):
    resp = client.post("/api/v1/projects", json={"name": name}, headers=_auth_header(token))
    assert resp.status_code == 201
    return resp.json()["id"]


def test_prompt_endpoints_require_auth() -> None:
    client, _ = build_test_client()
    fake_project_id = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/api/v1/projects/{fake_project_id}/prompts", json={"name": "x"}).status_code == 401
    assert client.get(f"/api/v1/projects/{fake_project_id}/prompts").status_code == 401


def test_create_list_get_prompt() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "alice@example.com")
    project_id = _create_project(client, token)

    create = client.post(
        f"/api/v1/projects/{project_id}/prompts",
        json={"name": "Greeting", "description": "Says hello"},
        headers=_auth_header(token),
    )
    assert create.status_code == 201
    prompt = create.json()
    assert prompt["name"] == "Greeting"
    assert prompt["project_id"] == project_id

    listing = client.get(f"/api/v1/projects/{project_id}/prompts", headers=_auth_header(token))
    assert listing.status_code == 200
    assert any(p["id"] == prompt["id"] for p in listing.json())

    get_one = client.get(f"/api/v1/projects/{project_id}/prompts/{prompt['id']}", headers=_auth_header(token))
    assert get_one.status_code == 200
    assert get_one.json()["name"] == "Greeting"


def test_duplicate_prompt_name_returns_409() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "bob@example.com")
    project_id = _create_project(client, token)

    payload = {"name": "Greeting"}
    first = client.post(f"/api/v1/projects/{project_id}/prompts", json=payload, headers=_auth_header(token))
    assert first.status_code == 201
    second = client.post(f"/api/v1/projects/{project_id}/prompts", json=payload, headers=_auth_header(token))
    assert second.status_code == 409


def test_patch_updates_only_provided_fields() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "carol@example.com")
    project_id = _create_project(client, token)

    created = client.post(
        f"/api/v1/projects/{project_id}/prompts",
        json={"name": "Greeting", "description": "Original"},
        headers=_auth_header(token),
    ).json()

    patched = client.patch(
        f"/api/v1/projects/{project_id}/prompts/{created['id']}",
        json={"description": "Updated"},
        headers=_auth_header(token),
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["name"] == "Greeting"
    assert body["description"] == "Updated"


def test_delete_prompt() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "dave@example.com")
    project_id = _create_project(client, token)

    created = client.post(
        f"/api/v1/projects/{project_id}/prompts", json={"name": "Greeting"}, headers=_auth_header(token)
    ).json()

    delete = client.delete(f"/api/v1/projects/{project_id}/prompts/{created['id']}", headers=_auth_header(token))
    assert delete.status_code == 204

    get_after = client.get(f"/api/v1/projects/{project_id}/prompts/{created['id']}", headers=_auth_header(token))
    assert get_after.status_code == 404


def test_non_owner_cannot_access_prompts() -> None:
    client, _ = build_test_client()
    owner_token = _register_and_login(client, "erin@example.com")
    other_token = _register_and_login(client, "frank@example.com")
    project_id = _create_project(client, owner_token)

    create_as_other = client.post(
        f"/api/v1/projects/{project_id}/prompts", json={"name": "Sneaky"}, headers=_auth_header(other_token)
    )
    assert create_as_other.status_code == 404

    list_as_other = client.get(f"/api/v1/projects/{project_id}/prompts", headers=_auth_header(other_token))
    assert list_as_other.status_code == 404
