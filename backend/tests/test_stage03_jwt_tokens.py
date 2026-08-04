from datetime import timedelta

import pytest
from jose import jwt
from jose.exceptions import JWTError

from app.core.config import settings
from app.domains.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_access_token_round_trip() -> None:
    token = create_access_token(subject="user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload


def test_refresh_token_round_trip() -> None:
    token = create_refresh_token(subject="user-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "refresh"


def test_tampered_token_raises() -> None:
    token = create_access_token(subject="user-123")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(JWTError):
        decode_token(tampered)


def test_wrong_secret_raises() -> None:
    bogus = jwt.encode({"sub": "user-123", "type": "access"}, "wrong-secret", algorithm=settings.jwt_algorithm)
    with pytest.raises(JWTError):
        decode_token(bogus)


def test_expired_token_raises() -> None:
    token = create_access_token(subject="user-123", expires_delta=timedelta(seconds=-1))
    with pytest.raises(JWTError):
        decode_token(token)


def test_tokens_for_same_subject_are_never_equal() -> None:
    # jose truncates iat/exp to whole seconds, so two tokens minted for the
    # same subject within the same second must still differ (e.g. via a
    # random jti claim) — otherwise stage 7's unique refresh-token-hash
    # constraint will collide under normal, fast-moving traffic.
    first_access = create_access_token(subject="user-123")
    second_access = create_access_token(subject="user-123")
    assert first_access != second_access

    first_refresh = create_refresh_token(subject="user-123")
    second_refresh = create_refresh_token(subject="user-123")
    assert first_refresh != second_refresh
