"""인증 서비스 (SDD §1.3 Service Layer, NFR-SEC-002)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.core.synonym_map import normalize_list
from app.models.orm import User
from app.schemas.auth import SignupRequest, UpdateProfileRequest


class AuthError(Exception):
    """인증 실패 (이메일 중복·비번 불일치 등)."""


async def signup(db: AsyncSession, req: SignupRequest) -> User:
    """회원가입 — 이메일 중복 검사 → bcrypt 해시 → INSERT."""
    existing = await db.scalar(select(User).where(User.email == req.email))
    if existing is not None:
        raise AuthError("이미 가입된 이메일입니다.")

    # NFR-EVAL-001 — 알레르기는 비교 전에 동의어 정규화하지 않으면 누출 가능.
    # 회원가입 시점에 정규화해 저장한다 (예: "달걀" → "계란").
    user = User(
        email=str(req.email),
        password_hash=hash_password(req.password),
        nickname=req.nickname,
        allergies=normalize_list(req.allergies or []),
        preferences={},
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    """로그인 — 이메일 조회 → bcrypt 검증."""
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("이메일 또는 비밀번호가 올바르지 않습니다.")
    return user


def issue_token(user: User) -> tuple[str, int]:
    """JWT 발급 후 (token, expires_in_seconds) 반환."""
    from app.core.security import JWT_EXPIRE_MIN

    token = create_access_token(subject=str(user.id), extra={"email": user.email})
    return token, JWT_EXPIRE_MIN * 60


async def update_profile(
    db: AsyncSession,
    user: User,
    req: UpdateProfileRequest,
) -> User:
    if req.new_password is not None:
        if not req.current_password or not verify_password(req.current_password, user.password_hash):
            raise AuthError("현재 비밀번호가 올바르지 않습니다.")
        user.password_hash = hash_password(req.new_password)  # NFR-SEC-001
    if req.nickname is not None:
        user.nickname = req.nickname
    await db.commit()
    await db.refresh(user)
    return user


async def update_allergies(
    db: AsyncSession,
    user: User,
    allergies: list[str],
) -> User:
    user.allergies = normalize_list(allergies)
    await db.commit()
    await db.refresh(user)
    return user
