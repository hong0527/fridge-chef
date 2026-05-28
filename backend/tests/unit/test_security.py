"""유닛 테스트 — security.py JWT 엣지 케이스 (SEC-004~006).

conftest.py 없이 단독 실행해도 import 성공하도록
파일 상단에서 환경변수를 직접 설정합니다.
"""
from __future__ import annotations

import os

# conftest 없이 단독 실행 시 security.py import 가드 충족
os.environ.setdefault(
    "JWT_SECRET",
    "test-secret-do-not-use-in-prod-padding-1234567890abcdef",
)
os.environ.setdefault("TESTING", "1")

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.security import JWT_ALGORITHM, JWT_SECRET, create_access_token, decode_access_token


class TestJWTEdgeCases:
    """SEC-004~006: 만료·변조·빈 토큰 엣지 케이스."""

    def test_sec004_expired_token_raises_expired_signature_error(self) -> None:
        """SEC-004: 만료된 토큰 → ExpiredSignatureError."""
        # NFR-SEC-001: JWT 토큰 만료 검증 — 만료된 토큰 접근 차단 보장
        payload = {
            "sub": "user-1",
            "iat": int((datetime.now(tz=UTC) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(tz=UTC) - timedelta(hours=1)).timestamp()),
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_sec005_tampered_token_raises_invalid_token_error(self) -> None:
        """SEC-005: 서명이 변조된 토큰 → InvalidTokenError."""
        # NFR-SEC-001: JWT 서명 무결성 검증 — 변조 토큰 위조 접근 차단 보장
        token = create_access_token("user-1")
        header, payload, _ = token.split(".")
        tampered = f"{header}.{payload}.invalidsignatureXXXXXXXXXXXXXXXX"
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(tampered)

    def test_sec006_empty_token_raises_decode_error(self) -> None:
        """SEC-006: 빈 문자열 토큰 → DecodeError."""
        # NFR-SEC-001: JWT 형식 검증 — 빈 토큰으로 인증 우회 차단 보장
        with pytest.raises(jwt.DecodeError):
            decode_access_token("")
