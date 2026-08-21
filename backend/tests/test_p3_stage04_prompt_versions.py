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


def _create_project_and_prompt(client, token, project_name="Proj A", prompt_name="Greeting"):
    project_id = client.post(
        "/api/v1/projects", json={"name": project_name}, headers=_auth_header(token)
    ).json()["id"]
    prompt_id = client.post(
        f"/api/v1/projects/{project_id}/prompts", json={"name": prompt_name}, headers=_auth_header(token)
    ).json()["id"]
    return project_id, prompt_id


def test_create_version_starts_at_one_and_increments() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "alice@example.com")
    project_id, prompt_id = _create_project_and_prompt(client, token)

    first = client.post(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/versions",
        json={"content": "Hello"},
        headers=_auth_header(token),
    )
    assert first.status_code == 201
    assert first.json()["version_number"] == 1

    second = client.post(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/versions",
        json={"content": "Hello there"},
        headers=_auth_header(token),
    )
    assert second.status_code == 201
    assert second.json()["version_number"] == 2


def test_list_versions_ordered_oldest_to_newest() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "bob@example.com")
    project_id, prompt_id = _create_project_and_prompt(client, token)

    for content in ["v1", "v2", "v3"]:
        client.post(
            f"/api/v1/projects/{project_id}/prompts/{prompt_id}/versions",
            json={"content": content},
            headers=_auth_header(token),
        )

    listing = client.get(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/versions", headers=_auth_header(token)
    )
    assert listing.status_code == 200
    numbers = [v["version_number"] for v in listing.json()]
    assert numbers == sorted(numbers)


def test_get_latest_version() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "carol@example.com")
    project_id, prompt_id = _create_project_and_prompt(client, token)

    client.post(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/versions",
        json={"content": "old"},
        headers=_auth_header(token),
    )
    client.post(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/versions",
        json={"content": "new"},
        headers=_auth_header(token),
    )

    latest = client.get(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/versions/latest", headers=_auth_header(token)
    )
    assert latest.status_code == 200
    assert latest.json()["content"] == "new"
    assert latest.json()["version_number"] == 2


def test_get_latest_version_404_when_no_versions_exist() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "dave@example.com")
    project_id, prompt_id = _create_project_and_prompt(client, token)

    response = client.get(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/versions/latest", headers=_auth_header(token)
    )
    assert response.status_code == 404


def test_get_specific_version_by_number() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "erin@example.com")
    project_id, prompt_id = _create_project_and_prompt(client, token)

    client.post(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/versions",
        json={"content": "v1 content"},
        headers=_auth_header(token),
    )

    response = client.get(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/versions/1", headers=_auth_header(token)
    )
    assert response.status_code == 200
    assert response.json()["content"] == "v1 content"

    missing = client.get(
        f"/api/v1/projects/{project_id}/prompts/{prompt_id}/versions/99", headers=_auth_header(token)
    )
    assert missing.status_code == 404
