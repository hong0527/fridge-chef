"""POST /api/auth/verify-email 엔드포인트 테스트 + 미인증 로그인 차단 (VE-001~005).

05b48e2 커밋에서 추가된 기능인데 test_auth_api.py에 검증이 0건.
- 이메일 인증 토큰 검증 4가지 경로 (VE-001~004)
- 미인증 사용자 로그인 차단 (VE-005)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.models.orm import User


class TestVerifyEmailEndpoint:
    """POST /api/auth/verify-email — VE-001~004."""

    async def test_ve001_valid_token_returns_200(self, async_client, db_session) -> None:
        """VE-001: 유효한 토큰 → 200 + is_email_verified=True."""
        resp = await async_client.post("/api/auth/signup", json={
            "email": "ve001@test.com", "password": "TestPass1!", "nickname": "테스터",
        })
        assert resp.status_code == 201

        user = await db_session.scalar(select(User).where(User.email == "ve001@test.com"))
        token = user.email_verification_token

        resp = await async_client.post("/api/auth/verify-email", json={"token": token})
        assert resp.status_code == 200
        assert resp.json()["is_email_verified"] is True

    async def test_ve002_already_verified_is_idempotent(
        self, async_client, db_session
    ) -> None:
        """VE-002: 이미 인증된 토큰 재호출 → 200 (멱등성)."""
        resp = await async_client.post("/api/auth/signup", json={
            "email": "ve002@test.com", "password": "TestPass1!", "nickname": "테스터",
        })
        assert resp.status_code == 201

        user = await db_session.scalar(select(User).where(User.email == "ve002@test.com"))
        token = user.email_verification_token

        first = await async_client.post("/api/auth/verify-email", json={"token": token})
        assert first.status_code == 200

        # 동일 토큰 재호출 → 오류 없이 200
        second = await async_client.post("/api/auth/verify-email", json={"token": token})
        assert second.status_code == 200
        assert second.json()["is_email_verified"] is True

    async def test_ve003_invalid_token_returns_400(self, async_client) -> None:
        """VE-003: 완전히 잘못된 토큰 → 400."""
        resp = await async_client.post(
            "/api/auth/verify-email", json={"token": "totally-invalid-token-xyz-abc"}
        )
        assert resp.status_code == 400

    async def test_ve004_expired_token_returns_400(self, async_client, db_session) -> None:
        """VE-004: 만료 토큰 (25시간 전으로 DB 조작) → 400."""
        resp = await async_client.post("/api/auth/signup", json={
            "email": "ve004@test.com", "password": "TestPass1!", "nickname": "테스터",
        })
        assert resp.status_code == 201

        user = await db_session.scalar(select(User).where(User.email == "ve004@test.com"))
        token = user.email_verification_token

        # 24시간 유효기간을 과거로 조작 (25시간 전)
        await db_session.execute(
            update(User).where(User.email == "ve004@test.com").values(
                email_verification_token_expires_at=datetime.now(tz=UTC) - timedelta(hours=25)
            )
        )
        await db_session.commit()

        resp = await async_client.post("/api/auth/verify-email", json={"token": token})
        assert resp.status_code == 400


class TestUnauthenticatedLogin:
    """VE-005: 이메일 미인증 사용자 로그인 차단."""

    async def test_ve005_unverified_user_login_blocked(self, async_client) -> None:
        """VE-005: 이메일 미인증 상태로 로그인 시도 → 403 + "이메일 인증" 메시지.

        NOTE: 요구사항 문서에는 401이 명시되어 있으나, auth.py:51에서
        "이메일 인증" 오류에 대해 HTTP 403을 반환하도록 구현되어 있음.
        """
        await async_client.post("/api/auth/signup", json={
            "email": "ve005@test.com", "password": "TestPass1!", "nickname": "미인증",
        })

        resp = await async_client.post("/api/auth/login", json={
            "email": "ve005@test.com", "password": "TestPass1!",
        })
        assert resp.status_code == 403
        assert "이메일 인증" in resp.json()["detail"]
