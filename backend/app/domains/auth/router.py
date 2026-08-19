import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose.exceptions import JWTError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import RefreshToken, User
from app.domains.auth.schemas import Token, UserCreate, UserRead, RefreshRequest
from app.domains.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter()

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))
    db.add(RefreshToken(
    user_id=user.id,
    token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
    expires_at=datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_ttl_days),))
    db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token)

@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user

@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    unauthorized = HTTPException(status_code=401, detail="Invalid refresh token")

    try:
        token_payload = decode_token(payload.refresh_token)
    except JWTError:
        raise unauthorized
    if token_payload.get("type") != "refresh":
        raise unauthorized

    token_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    stored = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > datetime.now(timezone.utc),
    ).first()
    if stored is None:
        raise unauthorized

    stored.revoked_at = datetime.now(timezone.utc)
    db.add(stored)
    db.commit()

    user = db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise unauthorized

    new_access_token = create_access_token(subject=str(user.id))
    new_refresh_token = create_refresh_token(subject=str(user.id))
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hashlib.sha256(new_refresh_token.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_ttl_days),
    ))
    db.commit()

    return Token(access_token=new_access_token, refresh_token=new_refresh_token)
