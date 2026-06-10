"""auth.py 라우터 함수 직접 호출 단위 테스트 — coverage 보완.

Python 3.13 + coverage.py sys.monitoring 버그 우회:
ASGI transport를 통한 호출 시 await 재개 지점의 LINE 이벤트가 발생하지 않으므로,
route 함수를 직접 호출해 coverage 추적 범위에 포함시킨다.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.api.auth as auth_mod
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    UpdateAllergiesRequest,
    UpdateProfileRequest,
    VerifyEmailRequest,
)
from app.services.auth_service import AuthError


def _make_db_user(
    id: int = 1,
    email: str = "unit@test.com",
    nickname: str = "유닛",
    allergies: list | None = None,
    is_email_verified: bool = True,
) -> MagicMock:
    u = MagicMock()
    u.id = id
    u.email = email
    u.nickname = nickname
    u.allergies = allergies or []
    u.is_email_verified = is_email_verified
    return u


class TestSignupRouterUnit:
    """signup() 라우터 직접 호출 — 정상/예외 분기 coverage."""

    async def test_success_returns_user_public(self, monkeypatch) -> None:
        # NFR-SEC-001 — UserPublic 응답에 password/password_hash 필드 미노출
        mock_user = _make_db_user(email="unit1@test.com", is_email_verified=False)
        monkeypatch.setattr(
            auth_mod.auth_service, "signup", AsyncMock(return_value=mock_user)
        )

        req = SignupRequest(email="unit1@test.com", password="Pass1234!", nickname="유닛1")
        result = await auth_mod.signup(req, AsyncMock())

        assert result.email == "unit1@test.com"
        assert result.id == 1
        assert result.is_email_verified is False

    async def test_duplicate_email_raises_409(self, monkeypatch) -> None:
        monkeypatch.setattr(
            auth_mod.auth_service,
            "signup",
            AsyncMock(side_effect=AuthError("이미 가입된 이메일입니다.")),
        )

        req = SignupRequest(email="dup@test.com", password="Pass1234!", nickname="중복")
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await auth_mod.signup(req, AsyncMock())
        assert exc.value.status_code == 409
        assert "detail" in exc.value.__dict__


class TestLoginRouterUnit:
    """login() 라우터 직접 호출 — 200/401/403 분기 coverage."""

    async def test_success_returns_token_response(self, monkeypatch) -> None:
        mock_user = _make_db_user()
        monkeypatch.setattr(
            auth_mod.auth_service, "authenticate", AsyncMock(return_value=mock_user)
        )
        monkeypatch.setattr(
            auth_mod.auth_service, "issue_token", MagicMock(return_value=("tok-xyz", 3600))
        )
        monkeypatch.setattr(auth_mod, "check_rate_limit", lambda _: None)
        monkeypatch.setattr(auth_mod, "clear_attempts", lambda _: None)

        req = LoginRequest(email="unit@test.com", password="Pass1234!")
        result = await auth_mod.login(req, AsyncMock())

        assert result.access_token == "tok-xyz"
        assert result.expires_in == 3600

    async def test_wrong_password_raises_401(self, monkeypatch) -> None:
        # NFR-SEC-003 — 잘못된 비밀번호 → record_failure 호출 경로 (5회 후 잠금 카운트)
        monkeypatch.setattr(
            auth_mod.auth_service,
            "authenticate",
            AsyncMock(side_effect=AuthError("비밀번호가 틀립니다.")),
        )
        monkeypatch.setattr(auth_mod, "check_rate_limit", lambda _: None)
        monkeypatch.setattr(auth_mod, "record_failure", lambda _: None)

        req = LoginRequest(email="unit@test.com", password="WrongPass!")
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await auth_mod.login(req, AsyncMock())
        assert exc.value.status_code == 401

    async def test_unverified_email_raises_403(self, monkeypatch) -> None:
        monkeypatch.setattr(
            auth_mod.auth_service,
            "authenticate",
            AsyncMock(side_effect=AuthError("이메일 인증이 완료되지 않았습니다.")),
        )
        monkeypatch.setattr(auth_mod, "check_rate_limit", lambda _: None)
        monkeypatch.setattr(auth_mod, "record_failure", lambda _: None)

        req = LoginRequest(email="unverified@test.com", password="Pass1234!")
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await auth_mod.login(req, AsyncMock())
        assert exc.value.status_code == 403


class TestVerifyEmailRouterUnit:
    """verify_email() 라우터 직접 호출 — 정상/예외 분기 coverage."""

    async def test_success_returns_verified_user(self, monkeypatch) -> None:
        mock_user = _make_db_user(is_email_verified=True)
        monkeypatch.setattr(
            auth_mod.auth_service, "verify_email", AsyncMock(return_value=mock_user)
        )

        req = VerifyEmailRequest(token="valid-token-abc")
        result = await auth_mod.verify_email(req, AsyncMock())

        assert result.is_email_verified is True

    async def test_invalid_token_raises_400(self, monkeypatch) -> None:
        monkeypatch.setattr(
            auth_mod.auth_service,
            "verify_email",
            AsyncMock(side_effect=AuthError("유효하지 않은 토큰입니다.")),
        )

        req = VerifyEmailRequest(token="bad-token")
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await auth_mod.verify_email(req, AsyncMock())
        assert exc.value.status_code == 400


class TestMeRouterUnit:
    """me() 라우터 직접 호출."""

    async def test_returns_user_public(self) -> None:
        mock_db_user = _make_db_user(id=42, email="me@test.com", nickname="나")
        result = await auth_mod.me(user=mock_db_user)

        assert result.id == 42
        assert result.email == "me@test.com"
        assert result.nickname == "나"


class TestUpdateMeRouterUnit:
    """update_me() 라우터 직접 호출 — 정상/예외 분기 coverage."""

    async def test_success_returns_updated_user(self, monkeypatch) -> None:
        updated_user = _make_db_user(nickname="수정됨")
        monkeypatch.setattr(
            auth_mod.auth_service, "update_profile", AsyncMock(return_value=updated_user)
        )

        req = UpdateProfileRequest(current_password="Pass1234!", new_password="NewPass1!")
        result = await auth_mod.update_me(req, _make_db_user(), AsyncMock())

        assert result.nickname == "수정됨"

    async def test_wrong_current_password_raises_400(self, monkeypatch) -> None:
        # NFR-SEC-001 — 비밀번호 변경: bcrypt 검증 실패 시 변경 거부 (auth_service.update_profile)
        monkeypatch.setattr(
            auth_mod.auth_service,
            "update_profile",
            AsyncMock(side_effect=AuthError("현재 비밀번호가 틀립니다.")),
        )

        req = UpdateProfileRequest(current_password="wrongpw!", new_password="NewPass1!")
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await auth_mod.update_me(req, _make_db_user(), AsyncMock())
        assert exc.value.status_code == 400
        assert "detail" in exc.value.__dict__


class TestUpdateMyAllergiesRouterUnit:
    """update_my_allergies() 라우터 직접 호출."""

    async def test_returns_user_with_updated_allergies(self, monkeypatch) -> None:
        # NFR-EXT-001 — 수집 개인정보(알레르기) 갱신 응답에 allergies 필드 정상 반환
        updated_user = _make_db_user(allergies=["땅콩", "우유"])
        monkeypatch.setattr(
            auth_mod.auth_service, "update_allergies", AsyncMock(return_value=updated_user)
        )

        req = UpdateAllergiesRequest(allergies=["땅콩", "우유"])
        result = await auth_mod.update_my_allergies(req, _make_db_user(), AsyncMock())

        assert sorted(result.allergies) == ["땅콩", "우유"]
