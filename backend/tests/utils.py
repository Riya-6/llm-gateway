"""Shared test harness for the staged auth milestone.

Each stage test file imports only the model modules it needs *before*
calling build_test_client(), so Base.metadata only contains the tables
that stage depends on. This keeps stage failures isolated: a missing
model surfaces as an ImportError pointing at the exact module you still
need to write, not an unrelated table-doesn't-exist error somewhere else.
"""

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.infrastructure.db.base import Base
from app.main import app


def build_test_client() -> tuple[TestClient, sessionmaker[Session]]:
    """Spin up an isolated in-memory SQLite DB and wire it into the app.

    Call this *after* importing whichever `app.domains.*.models` modules
    the current test needs, so their tables are registered on
    `Base.metadata` before `create_all` runs.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Iterator[Session]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return client, testing_session_local
