from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose.exceptions import JWTError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domains.auth.models import User
from app.domains.auth.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Check 1: is this a validly signed, non-expired token
    try:
        payload = decode_token(token)
    except JWTError:
        raise unauthorized

    # Check 2: reject refresh tokens here — only access tokens may authenticate requests.
    if payload.get("type") != "access":
        raise unauthorized

    # Check 3: the token stores the user id as plain text ("sub") — parse it back to a UUID.
    try:
        user_id = UUID(payload.get("sub"))
    except (TypeError, ValueError):
        raise unauthorized

    # Check 4: the token may still be valid while the user is gone or deactivated since it was issued.
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized

    # All checks passed — this is who's making the request.
    return user
