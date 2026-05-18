"""인증·암호화 유틸 (NFR-SEC-002 — bcrypt + JWT)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

_RAW_SECRET = os.getenv("JWT_SECRET", "")
# NFR-SEC-002: 보안 필수 — 부팅 시 약한 시크릿 거부 (테스트는 TESTING=1로 우회)
if not _RAW_SECRET and os.getenv("TESTING") != "1":
    raise RuntimeError(
        "JWT_SECRET 환경변수가 필수입니다. 32자 이상의 안전한 무작위 문자열을 설정하세요. "
        '예: python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )
if _RAW_SECRET and (len(_RAW_SECRET) < 32 or _RAW_SECRET.startswith("dev-")):
    raise RuntimeError(
        "JWT_SECRET이 너무 약합니다. 32자 이상의 무작위 문자열을 설정하세요."
    )
JWT_SECRET: str = _RAW_SECRET or "test-only-secret-do-not-use-in-prod-32chars"
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MIN: int = int(os.getenv("JWT_EXPIRE_MIN", "60"))  # 1h (refresh 토큰 패턴 권장)


def hash_password(plain: str) -> str:
    """bcrypt 해시 (work factor 12)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    """JWT 발급. subject 는 user_id."""
    now = datetime.now(tz=timezone.utc)
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
