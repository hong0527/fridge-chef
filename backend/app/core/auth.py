"""인증 의존성 (SDD §5 AuthService) — JWT 단일 출처.

NFR-SEC-002 — Bearer JWT 검증. 이전 X-User-Id 헤더 신뢰는 보안 결함이라 폐기.
SRS FR-007 — saved_allergies는 DB orm.User.allergies에서 로드.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import JWT_ALGORITHM, JWT_SECRET
from app.models.orm import User as DBUser


@dataclass
class User:
    user_id: str = "guest"
    saved_allergies: list[str] = field(default_factory=list)


async def _bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰이 필요합니다.")
    return authorization.split(" ", 1)[1].strip()


async def get_current_user(
    token: str = Depends(_bearer_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    """JWT 검증 후 DB에서 사용자·알레르기 로드."""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={
                "require": ["exp", "sub", "iat"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_signature": True,
            },
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 토큰") from exc

    row: DBUser | None = await db.scalar(select(DBUser).where(DBUser.id == user_id))
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "사용자를 찾을 수 없습니다.")
    return User(user_id=str(row.id), saved_allergies=list(row.allergies or []))


async def get_current_db_user(  # NFR-PERF-001
    token: str = Depends(_bearer_token),
    db: AsyncSession = Depends(get_db),
) -> DBUser:
    """회원정보·알레르기 수정 전용 Depends — 전체 ORM 객체 반환.

    기존 get_current_user와 JWT 검증 로직은 동일하나,
    경량 dataclass 대신 DBUser ORM 객체를 그대로 반환한다.
    password_hash 등 민감 필드가 포함되므로 이 Depends는
    프로필 수정 엔드포인트에서만 사용한다.
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={
                "require": ["exp", "sub", "iat"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_signature": True,
            },
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "유효하지 않은 토큰") from exc

    row: DBUser | None = await db.scalar(select(DBUser).where(DBUser.id == user_id))
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "사용자를 찾을 수 없습니다.")
    return row
