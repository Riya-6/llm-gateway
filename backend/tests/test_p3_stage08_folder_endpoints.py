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
    return client.post("/api/v1/projects", json={"name": name}, headers=_auth_header(token)).json()["id"]


def _create_prompt(client, token, project_id, name="Greeting"):
    return client.post(
        f"/api/v1/projects/{project_id}/prompts", json={"name": name}, headers=_auth_header(token)
    ).json()["id"]


def test_create_and_list_folders() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "alice@example.com")
    project_id = _create_project(client, token)

    create = client.post(
        f"/api/v1/projects/{project_id}/folders", json={"name": "Marketing"}, headers=_auth_header(token)
    )
    assert create.status_code == 201

    listing = client.get(f"/api/v1/projects/{project_id}/folders", headers=_auth_header(token))
    assert listing.status_code == 200
    assert any(f["name"] == "Marketing" for f in listing.json())


def test_assign_prompt_to_folder_via_patch() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "bob@example.com")
    project_id = _create_project(client, token)
    prompt_id = _create_prompt(client, token, project_id)
    folder_id = client.post(
        f"/api/v1/projects/{project_id}/folders", json={"name": "Marketing"}, headers=_auth_header(token)
    ).json()["id"]

    patched = client.patch(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}",
        json={"folder_id": folder_id},
        headers=_auth_header(token),
    )
    assert patched.status_code == 200
    assert patched.json()["folder_id"] == folder_id


def test_list_prompts_in_a_folder() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "carol@example.com")
    project_id = _create_project(client, token)
    prompt_id = _create_prompt(client, token, project_id)
    folder_id = client.post(
        f"/api/v1/projects/{project_id}/folders", json={"name": "Marketing"}, headers=_auth_header(token)
    ).json()["id"]
    client.patch(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}",
        json={"folder_id": folder_id},
        headers=_auth_header(token),
    )

    listing = client.get(f"/api/v1/projects/{project_id}/folders/{folder_id}/prompts", headers=_auth_header(token))
    assert listing.status_code == 200
    assert [p["id"] for p in listing.json()] == [prompt_id]


def test_assigning_folder_from_another_project_returns_404() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "dave@example.com")
    project_a = _create_project(client, token, "Proj A")
    project_b = _create_project(client, token, "Proj B")
    prompt_id = _create_prompt(client, token, project_a)
    foreign_folder_id = client.post(
        f"/api/v1/projects/{project_b}/folders", json={"name": "Other"}, headers=_auth_header(token)
    ).json()["id"]

    patched = client.patch(
        f"/api/v1/projects/{project_a}/prompts/{prompt_id}",
        json={"folder_id": foreign_folder_id},
        headers=_auth_header(token),
    )
    assert patched.status_code == 404


def test_explicit_null_clears_folder_assignment() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "erin@example.com")
    project_id = _create_project(client, token)
    prompt_id = _create_prompt(client, token, project_id)
    folder_id = client.post(
        f"/api/v1/projects/{project_id}/folders", json={"name": "Marketing"}, headers=_auth_header(token)
    ).json()["id"]
    client.patch(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}",
        json={"folder_id": folder_id},
        headers=_auth_header(token),
    )

    cleared = client.patch(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}",
        json={"folder_id": None},
        headers=_auth_header(token),
    )
    assert cleared.status_code == 200
    assert cleared.json()["folder_id"] is None
