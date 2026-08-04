from app.domains.auth import models as auth_models  # noqa: F401
from app.domains.projects import models as project_models  # noqa: F401
from tests.utils import build_test_client


def _register_and_login(client, email, password="hunter22"):
    client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    return login.json()["access_token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_projects_require_auth() -> None:
    client, _ = build_test_client()
    assert client.post("/api/v1/projects", json={"name": "x"}).status_code == 401
    assert client.get("/api/v1/projects").status_code == 401
    assert client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000").status_code == 401


def test_create_and_list_own_project() -> None:
    client, _ = build_test_client()
    token = _register_and_login(client, "ivy@example.com")

    create = client.post("/api/v1/projects", json={"name": "Gateway Prod"}, headers=_auth_header(token))
    assert create.status_code == 201
    project = create.json()
    assert project["name"] == "Gateway Prod"

    listing = client.get("/api/v1/projects", headers=_auth_header(token))
    assert listing.status_code == 200
    ids = [p["id"] for p in listing.json()]
    assert project["id"] in ids


def test_projects_are_isolated_between_users() -> None:
    client, _ = build_test_client()
    token_a = _register_and_login(client, "user-a@example.com")
    token_b = _register_and_login(client, "user-b@example.com")

    created = client.post("/api/v1/projects", json={"name": "A's project"}, headers=_auth_header(token_a))
    project_id = created.json()["id"]

    listing_b = client.get("/api/v1/projects", headers=_auth_header(token_b))
    assert listing_b.json() == []

    get_as_b = client.get(f"/api/v1/projects/{project_id}", headers=_auth_header(token_b))
    assert get_as_b.status_code == 404

    get_as_a = client.get(f"/api/v1/projects/{project_id}", headers=_auth_header(token_a))
    assert get_as_a.status_code == 200
