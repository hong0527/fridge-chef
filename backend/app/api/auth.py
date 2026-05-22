"""/api/auth/* — 회원가입·로그인 라우터.

# NFR-SEC-002 — bcrypt 해시 + JWT
# NFR-SEC-001 — 비밀키는 환경변수로만 주입
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_db_user
from app.core.db import get_db
from app.core.rate_limit import check_rate_limit, clear_attempts, record_failure
from app.models.orm import User as DBUser
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    UpdateAllergiesRequest,
    UpdateProfileRequest,
    UserPublic,
)
from app.services import auth_service
from app.services.auth_service import AuthError

router = APIRouter()


@router.post("/signup", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def signup(req: SignupRequest, db: AsyncSession = Depends(get_db)) -> UserPublic:
    try:
        user = await auth_service.signup(db, req)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    return UserPublic(
        id=user.id, email=user.email, nickname=user.nickname, allergies=user.allergies
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    check_rate_limit(str(req.email))  # NFR-SEC-003
    try:
        user = await auth_service.authenticate(db, str(req.email), req.password)
    except AuthError as e:
        record_failure(str(req.email))  # NFR-SEC-003
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    clear_attempts(str(req.email))
    token, expires_in = auth_service.issue_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserPublic)  # NFR-PERF-001
async def me(user: DBUser = Depends(get_current_db_user)) -> UserPublic:
    return UserPublic(
        id=user.id, email=user.email, nickname=user.nickname, allergies=user.allergies
    )


@router.patch("/me", response_model=UserPublic)  # NFR-SEC-001
async def update_me(
    req: UpdateProfileRequest,
    user: DBUser = Depends(get_current_db_user),
    db: AsyncSession = Depends(get_db),
) -> UserPublic:
    try:
        user = await auth_service.update_profile(db, user, req)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return UserPublic(
        id=user.id, email=user.email, nickname=user.nickname, allergies=user.allergies
    )


@router.patch("/me/allergies", response_model=UserPublic)
async def update_my_allergies(
    req: UpdateAllergiesRequest,
    user: DBUser = Depends(get_current_db_user),
    db: AsyncSession = Depends(get_db),
) -> UserPublic:
    user = await auth_service.update_allergies(db, user, req.allergies)
    return UserPublic(
        id=user.id, email=user.email, nickname=user.nickname, allergies=user.allergies
    )
