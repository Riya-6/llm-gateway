from app.domains.auth import models as auth_models
from app.domains.generation import models as generation_models
from app.domains.projects import models as project_models
from tests.utils import build_test_client


def _make_user_and_project(db):
    user = auth_models.User(email="owner@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    db.refresh(user)

    project = project_models.Project(name="Proj A", owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return user, project


def test_create_request_and_response() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)

        request = generation_models.GenerationRequest(
            project_id=project.id,
            model="mock-model",
            status="succeeded",
            created_by=user.id,
        )
        db.add(request)
        db.commit()
        db.refresh(request)

        response = generation_models.GenerationResponse(
            request_id=request.id,
            provider="primary",
            model="mock-model",
            content="hello",
            tokens_used=5,
            latency_ms=10,
        )
        db.add(response)
        db.commit()
        db.refresh(response)

        assert response.request_id == request.id
        assert response.content == "hello"
    finally:
        db.close()


def test_deleting_request_cascades_to_its_response() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)

        request = generation_models.GenerationRequest(
            project_id=project.id,
            model="mock-model",
            status="succeeded",
            created_by=user.id,
        )
        db.add(request)
        db.commit()
        db.refresh(request)

        db.add(
            generation_models.GenerationResponse(
                request_id=request.id,
                provider="primary",
                model="mock-model",
                content="hello",
                tokens_used=5,
                latency_ms=10,
            )
        )
        db.commit()

        db.delete(request)
        db.commit()

        remaining = (
            db.query(generation_models.GenerationResponse)
            .filter(generation_models.GenerationResponse.request_id == request.id)
            .all()
        )
        assert remaining == []
    finally:
        db.close()
