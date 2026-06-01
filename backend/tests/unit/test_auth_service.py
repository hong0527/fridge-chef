"""auth_service.py 직접 단위 테스트 — 서비스 레이어 커버리지 보강.

ASGI Transport를 거치는 API 테스트는 FastAPI가 별도 asyncio Task를 생성하여
coverage.py가 Task 경계 너머의 코루틴 재개 지점을 추적하지 못한다.
이 파일은 auth_service 함수를 직접 await하여 해당 문제를 우회한다.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import User
from app.schemas.auth import SignupRequest, UpdateProfileRequest
from app.services import auth_service
from app.services.auth_service import AuthError

# ─── helpers ──────────────────────────────────────────────────

async def _make_verified_user(
    db: AsyncSession,
    email: str = "svc@test.com",
    password: str = "TestPass1!",
    nickname: str = "서비스테스터",
) -> User:
    req = SignupRequest(email=email, password=password, nickname=nickname)
    user = await auth_service.signup(db, req)
    await db.execute(update(User).where(User.email == email).values(is_email_verified=True))
    await db.commit()
    await db.refresh(user)
    return user


# ─── signup ───────────────────────────────────────────────────

class TestSignupDirect:
    async def test_creates_user_with_token(self, db_session: AsyncSession) -> None:
        # NFR-SEC-001: 비밀번호는 bcrypt 해시로 저장, 평문 저장 금지
        req = SignupRequest(email="new@test.com", password="Pass1234!", nickname="신규")
        user = await auth_service.signup(db_session, req)
        assert user.email == "new@test.com"
        assert not user.is_email_verified
        assert user.email_verification_token is not None

    async def test_duplicate_email_raises(self, db_session: AsyncSession) -> None:
        req = SignupRequest(email="dup@test.com", password="Pass1234!", nickname="중복")
        await auth_service.signup(db_session, req)
        with pytest.raises(AuthError, match="이미 가입된"):
            await auth_service.signup(
                db_session,
                SignupRequest(email="dup@test.com", password="Pass1234!", nickname="중복2"),
            )

    async def test_allergies_normalized(self, db_session: AsyncSession) -> None:
        # NFR-EXT-001: 수집 개인정보(알레르기)는 동의어 정규화 후 저장
        req = SignupRequest(
            email="allergy@test.com",
            password="Pass1234!",
            nickname="알레르기",
            allergies=["달걀"],
        )
        user = await auth_service.signup(db_session, req)
        assert "계란" in user.allergies


# ─── verify_email ─────────────────────────────────────────────

class TestVerifyEmailDirect:
    async def test_valid_token_sets_verified(self, db_session: AsyncSession) -> None:
        req = SignupRequest(email="ve@test.com", password="Pass1234!", nickname="인증")
        user = await auth_service.signup(db_session, req)
        token = user.email_verification_token
        verified = await auth_service.verify_email(db_session, token)
        assert verified.is_email_verified is True

    async def test_already_verified_is_idempotent(self, db_session: AsyncSession) -> None:
        req = SignupRequest(email="ve2@test.com", password="Pass1234!", nickname="멱등")
        user = await auth_service.signup(db_session, req)
        token = user.email_verification_token
        await auth_service.verify_email(db_session, token)
        result = await auth_service.verify_email(db_session, token)
        assert result.is_email_verified is True

    async def test_invalid_token_raises(self, db_session: AsyncSession) -> None:
        with pytest.raises(AuthError, match="유효하지 않은"):
            await auth_service.verify_email(db_session, "totally-invalid-token")

    async def test_expired_token_raises(self, db_session: AsyncSession) -> None:
        req = SignupRequest(email="ve3@test.com", password="Pass1234!", nickname="만료")
        user = await auth_service.signup(db_session, req)
        token = user.email_verification_token
        await db_session.execute(
            update(User).where(User.email == "ve3@test.com").values(
                email_verification_token_expires_at=datetime.now(tz=UTC) - timedelta(hours=25)
            )
        )
        await db_session.commit()
        with pytest.raises(AuthError, match="만료"):
            await auth_service.verify_email(db_session, token)


# ─── authenticate ─────────────────────────────────────────────

class TestAuthenticateDirect:
    async def test_success_returns_user(self, db_session: AsyncSession) -> None:
        # NFR-SEC-001: bcrypt 검증 통과 시 로그인 성공
        user = await _make_verified_user(db_session, "auth@test.com", "Pass1234!")
        result = await auth_service.authenticate(db_session, "auth@test.com", "Pass1234!")
        assert result.id == user.id

    async def test_wrong_password_raises(self, db_session: AsyncSession) -> None:
        # NFR-SEC-001: bcrypt 검증 실패 시 로그인 거부
        await _make_verified_user(db_session, "auth2@test.com", "Pass1234!")
        with pytest.raises(AuthError, match="비밀번호"):
            await auth_service.authenticate(db_session, "auth2@test.com", "WrongPass!")

    async def test_unverified_user_raises(self, db_session: AsyncSession) -> None:
        req = SignupRequest(email="unv@test.com", password="Pass1234!", nickname="미인증")
        await auth_service.signup(db_session, req)
        with pytest.raises(AuthError, match="이메일 인증"):
            await auth_service.authenticate(db_session, "unv@test.com", "Pass1234!")

    async def test_nonexistent_email_raises(self, db_session: AsyncSession) -> None:
        # NFR-SEC-001: 존재하지 않는 계정 — 인증 거부
        with pytest.raises(AuthError):
            await auth_service.authenticate(db_session, "ghost@test.com", "Pass1234!")


# ─── issue_token ──────────────────────────────────────────────

class TestIssueToken:
    async def test_returns_jwt_and_expiry(self, db_session: AsyncSession) -> None:
        # NFR-SEC-001: JWT 발급 — 3-part 형식(header.payload.signature) 검증
        user = await _make_verified_user(db_session, "tok@test.com")
        token, expires_in = auth_service.issue_token(user)
        assert token.count(".") == 2
        assert expires_in > 0


# ─── update_profile ───────────────────────────────────────────

class TestUpdateProfileDirect:
    async def test_nickname_change(self, db_session: AsyncSession) -> None:
        user = await _make_verified_user(db_session, "prof@test.com")
        req = UpdateProfileRequest(nickname="새닉네임")
        updated = await auth_service.update_profile(db_session, user, req)
        assert updated.nickname == "새닉네임"

    async def test_password_change_success(self, db_session: AsyncSession) -> None:
        # NFR-SEC-001: 비밀번호 변경 시 새 비밀번호를 bcrypt 재해시하여 저장
        user = await _make_verified_user(db_session, "prof2@test.com", "OldPass1!")
        req = UpdateProfileRequest(current_password="OldPass1!", new_password="NewPass1!")
        updated = await auth_service.update_profile(db_session, user, req)
        assert updated is not None

    async def test_wrong_current_password_raises(self, db_session: AsyncSession) -> None:
        # NFR-SEC-001: 현재 비밀번호 bcrypt 검증 실패 시 변경 거부
        user = await _make_verified_user(db_session, "prof3@test.com", "OldPass1!")
        req = UpdateProfileRequest(current_password="WrongPass!", new_password="NewPass1!")
        with pytest.raises(AuthError, match="비밀번호"):
            await auth_service.update_profile(db_session, user, req)


# ─── update_allergies ─────────────────────────────────────────

class TestUpdateAllergiesDirect:
    async def test_updates_and_normalizes(self, db_session: AsyncSession) -> None:
        # NFR-EXT-001: 수집 개인정보(알레르기)는 동의어 정규화 후 저장
        user = await _make_verified_user(db_session, "alg@test.com")
        updated = await auth_service.update_allergies(db_session, user, ["달걀", "우유"])
        assert "계란" in updated.allergies
        assert "우유" in updated.allergies

    async def test_clear_allergies(self, db_session: AsyncSession) -> None:
        # NFR-EXT-001: 알레르기 개인정보 전체 초기화 반영
        user = await _make_verified_user(db_session, "alg2@test.com")
        await auth_service.update_allergies(db_session, user, ["계란"])
        updated = await auth_service.update_allergies(db_session, user, [])
        assert updated.allergies == []
