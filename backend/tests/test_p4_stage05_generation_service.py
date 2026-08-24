import pytest

from app.domains.auth import models as auth_models
from app.domains.generation import models as generation_models
from app.domains.generation.providers.base import GenerationError, ProviderResponse
from app.domains.generation.service import execute_generation
from app.domains.projects import models as project_models
from tests.utils import build_test_client


class _FakeProvider:
    name = "fake"

    def __init__(self, fail_times: int = 0, always_fail: bool = False) -> None:
        self.fail_times = fail_times
        self.always_fail = always_fail
        self.call_count = 0

    def generate(self, prompt: str, model: str) -> ProviderResponse:
        self.call_count += 1
        if self.always_fail or self.call_count <= self.fail_times:
            raise GenerationError(f"fake failed on attempt {self.call_count}")
        return ProviderResponse(provider=self.name, model=model, content="hi there", tokens_used=5, latency_ms=1)


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


def test_successful_generation_persists_request_and_response() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)
        provider = _FakeProvider()

        response = execute_generation(
            db,
            project_id=project.id,
            created_by=user.id,
            prompt="say hi",
            model="mock-model",
            provider=provider,
        )

        assert response.content == "hi there"
        assert response.provider == "fake"

        request = db.query(generation_models.GenerationRequest).filter(
            generation_models.GenerationRequest.id == response.request_id
        ).first()
        assert request is not None
        assert request.status == "succeeded"
    finally:
        db.close()


def test_retry_is_actually_used_not_bypassed() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)
        provider = _FakeProvider(fail_times=2)

        response = execute_generation(
            db,
            project_id=project.id,
            created_by=user.id,
            prompt="say hi",
            model="mock-model",
            provider=provider,
            max_attempts=3,
            base_backoff_seconds=0.0,
            jitter=False,
            sleep_fn=lambda _: None,
        )

        assert response is not None
        assert provider.call_count == 3

        request = db.query(generation_models.GenerationRequest).filter(
            generation_models.GenerationRequest.id == response.request_id
        ).first()
        assert request.status == "succeeded"
    finally:
        db.close()


def test_failed_generation_marks_request_failed_and_persists_no_response() -> None:
    _, SessionLocal = build_test_client()
    db = SessionLocal()
    try:
        user, project = _make_user_and_project(db)
        provider = _FakeProvider(always_fail=True)

        with pytest.raises(GenerationError):
            execute_generation(
                db,
                project_id=project.id,
                created_by=user.id,
                prompt="say hi",
                model="mock-model",
                provider=provider,
            )

        request = db.query(generation_models.GenerationRequest).filter(
            generation_models.GenerationRequest.project_id == project.id
        ).first()
        assert request is not None
        assert request.status == "failed"

        responses = db.query(generation_models.GenerationResponse).all()
        assert responses == []
    finally:
        db.close()
