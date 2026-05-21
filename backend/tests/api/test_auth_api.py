"""인증 API 통합 테스트 — SRS FR-001~003, NFR-SEC-002·003.

- FR-001 회원가입 (이메일+비밀번호+닉네임)
- FR-002 로그인 (JWT 발급)
- FR-003 비밀번호 재설정 (현재 스키마 미구현 → xfail 자리표시자)
- NFR-SEC-002: bcrypt 해시 저장, JWT HS256
- NFR-SEC-003: 5회 연속 실패 시 30분 잠금 (현재 미구현 → xfail)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest


# ─────────────────────────────────────────────────────────────
class TestSignup:
    """POST /api/auth/signup — FR-001."""

    async def test_signup_success_returns_201_and_public_fields(self, async_client) -> None:
        """# FR-001 — 정상 회원가입 → 201 + 비밀번호 미노출."""
        payload = {
            "email": "alice@fridgechef.io",
            "password": "AlicePass1!",
            "nickname": "앨리스",
            "allergies": ["계란"],
        }
        resp = await async_client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "alice@fridgechef.io"
        assert body["nickname"] == "앨리스"
        assert body["allergies"] == ["계란"]
        assert "id" in body and isinstance(body["id"], int)
        # NFR-SEC-002: 비밀번호 필드는 응답에 절대 노출 금지
        assert "password" not in body
        assert "password_hash" not in body

    async def test_signup_duplicate_email_returns_409(self, async_client, test_user) -> None:
        """# FR-001 — 중복 이메일 → 409."""
        resp = await async_client.post(
            "/api/auth/signup",
            json={
                "email": test_user["email"],
                "password": "Another1!",
                "nickname": "다른사람",
            },
        )
        assert resp.status_code == 409

    async def test_signup_invalid_email_format_returns_422(self, async_client) -> None:
        """# FR-001 — 잘못된 이메일 형식 → 422 (Pydantic EmailStr)."""
        resp = await async_client.post(
            "/api/auth/signup",
            json={"email": "not-an-email", "password": "Valid123!", "nickname": "x"},
        )
        assert resp.status_code == 422

    async def test_signup_password_too_short_returns_422(self, async_client) -> None:
        """# FR-001 — 비밀번호 < 8자 → 422 (Pydantic min_length=8)."""
        resp = await async_client.post(
            "/api/auth/signup",
            json={"email": "short@fridgechef.io", "password": "abc12", "nickname": "x"},
        )
        assert resp.status_code == 422

    async def test_signup_missing_nickname_returns_422(self, async_client) -> None:
        """# FR-001 — 필수 닉네임 누락 → 422."""
        resp = await async_client.post(
            "/api/auth/signup",
            json={"email": "noname@fridgechef.io", "password": "Valid123!"},
        )
        assert resp.status_code == 422

    async def test_signup_stores_bcrypt_hash_not_plain(
        self, async_client, db_session
    ) -> None:
        """# NFR-SEC-002 — bcrypt 해시 저장 확인 (raw 비교는 실패해야)."""
        from sqlalchemy import select

        from app.models.orm import User

        payload = {
            "email": "hash@fridgechef.io",
            "password": "PlainPass1!",
            "nickname": "해시테스트",
        }
        resp = await async_client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 201

        # 다른 세션에서 DB 조회
        user = await db_session.scalar(select(User).where(User.email == payload["email"]))
        assert user is not None
        # raw 비교 실패해야 함 (NFR-SEC-002)
        assert user.password_hash != payload["password"]
        # bcrypt 해시 prefix 검증 ($2a/$2b/$2y)
        assert user.password_hash.startswith("$2"), "bcrypt 해시 prefix 누락"


# ─────────────────────────────────────────────────────────────
class TestLogin:
    """POST /api/auth/login — FR-002."""

    async def test_login_success_returns_jwt(self, async_client, test_user) -> None:
        """# FR-002 — 정상 로그인 → JWT 토큰 발급."""
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0
        # JWT 형식: header.payload.signature
        assert body["access_token"].count(".") == 2

    async def test_login_wrong_password_returns_401(self, async_client, test_user) -> None:
        """# FR-002 — 잘못된 비밀번호 → 401."""
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": test_user["email"], "password": "Wrong999!"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_email_returns_401(self, async_client) -> None:
        """# FR-002 — 존재하지 않는 이메일 → 401 (사용자 열거 방지)."""
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": "ghost@fridgechef.io", "password": "Anything1!"},
        )
        assert resp.status_code == 401

    async def test_jwt_contains_user_id_subject(self, async_client, test_user) -> None:
        """# NFR-SEC-002 — JWT payload에 sub=user_id 포함."""
        import os

        secret = os.environ["JWT_SECRET"]
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )
        token = resp.json()["access_token"]
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        assert "sub" in payload
        assert int(payload["sub"]) == test_user["id"]
        assert "exp" in payload and "iat" in payload

    async def test_jwt_expired_token_rejected(self, async_client) -> None:
        """# NFR-SEC-002 — 만료된 JWT → 401 (fridge 등 보호 라우터에서 검증)."""
        import os

        secret = os.environ["JWT_SECRET"]
        past = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        expired_token = jwt.encode(
            {"sub": "1", "exp": int(past.timestamp())}, secret, algorithm="HS256"
        )
        resp = await async_client.get(
            "/api/fridge", headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert resp.status_code == 401

    @pytest.mark.xfail(
        reason="NFR-SEC-003 5회 실패 시 30분 잠금은 auth_service 미구현 (백오프 카운터 + Redis/DB 필요)",
        strict=False,
    )
    async def test_login_brute_force_lockout_after_5_failures(
        self, async_client, test_user
    ) -> None:
        """# NFR-SEC-003 — 5회 연속 실패 → 30분 잠금."""
        for _ in range(5):
            resp = await async_client.post(
                "/api/auth/login",
                json={"email": test_user["email"], "password": "Wrong999!"},
            )
            assert resp.status_code == 401
        # 6번째: 올바른 비번이어도 잠금
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )
        assert resp.status_code in (423, 429), "잠금 응답 (Locked / Too Many Requests)"


# ─────────────────────────────────────────────────────────────
class TestPasswordReset:
    """비밀번호 재설정 — FR-003 (현재 API 미구현)."""

    @pytest.mark.xfail(
        reason="FR-003 비밀번호 재설정 API는 본 MVP 라우터 스캐폴드에 미구현 (이메일 토큰 발송 필요)",
        strict=False,
    )
    async def test_password_reset_request_sends_token(self, async_client, test_user) -> None:
        """# FR-003 — 재설정 토큰 발급 요청 → 200."""
        resp = await async_client.post(
            "/api/auth/password-reset/request", json={"email": test_user["email"]}
        )
        assert resp.status_code == 200
