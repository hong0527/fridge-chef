"""email_service.py 격리 단위 테스트 — TESTING 분기, EmailError 전파, 예외 삼킴 (ES-001~003)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.email_service import EmailError, send_verification_email


class TestSendVerificationEmail:
    """send_verification_email — SMTP 격리 테스트."""

    def test_es001_testing_env_skips_smtp(self, monkeypatch) -> None:
        """ES-001: TESTING=1 환경 → SMTP 호출 없이 즉시 리턴."""
        monkeypatch.setenv("TESTING", "1")
        with patch("smtplib.SMTP") as mock_smtp:
            send_verification_email("test@test.com", "dummy-token")
            mock_smtp.assert_not_called()

    def test_es002_smtp_failure_raises_email_error(self, monkeypatch) -> None:
        """ES-002: SMTP 연결 실패 → EmailError 발생."""
        monkeypatch.delenv("TESTING", raising=False)
        with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("연결 거부")):
            with pytest.raises(EmailError):
                send_verification_email("test@test.com", "dummy-token")


class TestSignupEmailErrorSwallow:
    """ES-003: signup() 내 EmailError 예외 삼킴."""

    async def test_es003_signup_swallows_email_error(
        self, async_client, monkeypatch
    ) -> None:
        """ES-003: 이메일 발송 실패해도 signup() → 201 반환.

        auth_service는 send_verification_email을 직접 임포트하므로
        auth_service 모듈 내의 참조를 패치해야 한다.
        """
        import app.services.auth_service as auth_svc

        def _raise(*args, **kwargs) -> None:
            raise EmailError("SMTP 실패")

        monkeypatch.setattr(auth_svc, "send_verification_email", _raise)

        resp = await async_client.post("/api/auth/signup", json={
            "email": "es003@test.com", "password": "TestPass1!", "nickname": "테스터",
        })
        assert resp.status_code == 201
