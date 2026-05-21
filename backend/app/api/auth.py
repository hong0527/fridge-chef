"""/api/auth/* — 회원가입·로그인 라우터.

# NFR-SEC-002 — bcrypt 해시 + JWT
# NFR-SEC-001 — 비밀키는 환경변수로만 주입
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserPublic
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
    try:
        user = await auth_service.authenticate(db, str(req.email), req.password)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    token, expires_in = auth_service.issue_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in)
