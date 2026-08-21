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


def _create_project(client, token):
    return client.post("/api/v1/projects", json={"name": "Proj A"}, headers=_auth_header(token)).json()["id"]


def _create_prompt(client, token, project_id, name, description=None):
    return client.post(
        f"/api/v1/projects/{project_id}/prompts",
        json={"name": name, "description": description},
        headers=_auth_header(token),
    ).json()


def test_search_matches_name_case_insensitively() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "alice@example.com")
    project_id = _create_project(client, token)
    _create_prompt(client, token, project_id, "Customer Greeting")
    _create_prompt(client, token, project_id, "Order Confirmation")

    response = client.get(
        f"/api/v1/projects/{project_id}/prompts", params={"search": "greeting"}, headers=_auth_header(token)
    )
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert names == ["Customer Greeting"]


def test_search_matches_description_too() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "bob@example.com")
    project_id = _create_project(client, token)
    _create_prompt(client, token, project_id, "Prompt A", description="handles refunds")
    _create_prompt(client, token, project_id, "Prompt B", description="handles shipping")

    response = client.get(
        f"/api/v1/projects/{project_id}/prompts", params={"search": "refund"}, headers=_auth_header(token)
    )
    names = [p["name"] for p in response.json()]
    assert names == ["Prompt A"]


def test_filter_by_tag() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "carol@example.com")
    project_id = _create_project(client, token)
    tagged = _create_prompt(client, token, project_id, "Tagged Prompt")
    _create_prompt(client, token, project_id, "Untagged Prompt")

    tag_id = client.post(
        f"/api/v1/projects/{project_id}/tags", json={"name": "urgent"}, headers=_auth_header(token)
    ).json()["id"]
    client.post(
        f"/api/v1/projects/{project_id}/prompts/{tagged['id']}/tags/{tag_id}", headers=_auth_header(token)
    )

    response = client.get(
        f"/api/v1/projects/{project_id}/prompts", params={"tag": "urgent"}, headers=_auth_header(token)
    )
    names = [p["name"] for p in response.json()]
    assert names == ["Tagged Prompt"]


def test_filter_by_folder() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "dave@example.com")
    project_id = _create_project(client, token)
    filed = _create_prompt(client, token, project_id, "Filed Prompt")
    _create_prompt(client, token, project_id, "Unfiled Prompt")

    folder_id = client.post(
        f"/api/v1/projects/{project_id}/folders", json={"name": "Marketing"}, headers=_auth_header(token)
    ).json()["id"]
    client.patch(
        f"/api/v1/projects/{project_id}/prompts/{filed['id']}",
        json={"folder_id": folder_id},
        headers=_auth_header(token),
    )

    response = client.get(
        f"/api/v1/projects/{project_id}/prompts", params={"folder_id": folder_id}, headers=_auth_header(token)
    )
    names = [p["name"] for p in response.json()]
    assert names == ["Filed Prompt"]


def test_no_filters_returns_everything() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "erin@example.com")
    project_id = _create_project(client, token)
    _create_prompt(client, token, project_id, "Prompt A")
    _create_prompt(client, token, project_id, "Prompt B")

    response = client.get(f"/api/v1/projects/{project_id}/prompts", headers=_auth_header(token))
    assert len(response.json()) == 2
