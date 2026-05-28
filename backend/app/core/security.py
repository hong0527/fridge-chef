"""인증·암호화 유틸 (NFR-SEC-001 — bcrypt 비밀번호 해시 + JWT 토큰 발급)."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt


def _resolve_jwt_secret() -> str:
    """NFR-SEC-001: 부팅 시 약한 JWT 시크릿 거부. 함수로 감싸 테스트 시 monkeypatch 가능."""
    raw = os.getenv("JWT_SECRET", "")
    testing = os.getenv("TESTING") == "1"
    if not raw and not testing:
        raise RuntimeError(
            "JWT_SECRET 환경변수가 필수입니다. 32자 이상의 안전한 무작위 문자열을 설정하세요. "
            '예: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    if raw and (len(raw) < 32 or raw.startswith("dev-")):
        raise RuntimeError(
            "JWT_SECRET이 너무 약합니다. 32자 이상의 무작위 문자열을 설정하세요."
        )
    return raw or "test-only-secret-do-not-use-in-prod-32chars"


JWT_SECRET: str = _resolve_jwt_secret()
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MIN: int = int(os.getenv("JWT_EXPIRE_MIN", "60"))  # 1h (refresh 토큰 패턴 권장)


_BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))


def hash_password(plain: str) -> str:
    """bcrypt 해시 — 운영: rounds=12, 테스트: BCRYPT_ROUNDS=4."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    """JWT 발급. subject 는 user_id."""
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MIN)).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """JWT 검증 + 디코드. 실패 시 jwt.PyJWTError 전파."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
