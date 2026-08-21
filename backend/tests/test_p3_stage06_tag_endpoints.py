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


def _create_project_and_prompt(client, token):
    project_id = client.post("/api/v1/projects", json={"name": "Proj A"}, headers=_auth_header(token)).json()["id"]
    prompt_id = client.post(
        f"/api/v1/projects/{project_id}/prompts", json={"name": "Greeting"}, headers=_auth_header(token)
    ).json()["id"]
    return project_id, prompt_id


def test_create_and_list_tags() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "alice@example.com")
    project_id, _ = _create_project_and_prompt(client, token)

    create = client.post(f"/api/v1/projects/{project_id}/tags", json={"name": "marketing"}, headers=_auth_header(token))
    assert create.status_code == 201

    listing = client.get(f"/api/v1/projects/{project_id}/tags", headers=_auth_header(token))
    assert listing.status_code == 200
    assert any(t["name"] == "marketing" for t in listing.json())


def test_duplicate_tag_name_returns_409() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "bob@example.com")
    project_id, _ = _create_project_and_prompt(client, token)

    payload = {"name": "marketing"}
    first = client.post(f"/api/v1/projects/{project_id}/tags", json=payload, headers=_auth_header(token))
    assert first.status_code == 201
    second = client.post(f"/api/v1/projects/{project_id}/tags", json=payload, headers=_auth_header(token))
    assert second.status_code == 409


def test_attach_and_detach_tag_on_prompt() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "carol@example.com")
    project_id, prompt_id = _create_project_and_prompt(client, token)
    tag_id = client.post(
        f"/api/v1/projects/{project_id}/tags", json={"name": "marketing"}, headers=_auth_header(token)
    ).json()["id"]

    attach = client.post(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/tags/{tag_id}", headers=_auth_header(token)
    )
    assert attach.status_code == 204

    prompt_tags = client.get(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/tags", headers=_auth_header(token)
    )
    assert prompt_tags.status_code == 200
    assert any(t["id"] == tag_id for t in prompt_tags.json())

    detach = client.delete(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/tags/{tag_id}", headers=_auth_header(token)
    )
    assert detach.status_code == 204

    prompt_tags_after = client.get(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/tags", headers=_auth_header(token)
    )
    assert prompt_tags_after.json() == []


def test_attaching_same_tag_twice_is_idempotent() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "dave@example.com")
    project_id, prompt_id = _create_project_and_prompt(client, token)
    tag_id = client.post(
        f"/api/v1/projects/{project_id}/tags", json={"name": "marketing"}, headers=_auth_header(token)
    ).json()["id"]

    first = client.post(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/tags/{tag_id}", headers=_auth_header(token)
    )
    second = client.post(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/tags/{tag_id}", headers=_auth_header(token)
    )
    assert first.status_code == 204
    assert second.status_code == 204
