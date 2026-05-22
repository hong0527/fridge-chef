"""로그인 실패 횟수 제한 (NFR-SEC-003).

단일 워커 기준 인메모리 구현.
다중 워커 또는 재시작 후 초기화가 허용되지 않는 환경에서는
Redis 기반으로 교체 필요 (docker-compose에 Redis 포함됨).
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, status

_MAX_ATTEMPTS = 5
_LOCKOUT_SECONDS = 30 * 60  # 30분

# email → 실패 timestamp 목록
_attempts: dict[str, list[float]] = defaultdict(list)


def _purge_old(email: str, now: float) -> None:
    cutoff = now - _LOCKOUT_SECONDS
    _attempts[email] = [t for t in _attempts[email] if t > cutoff]


def check_rate_limit(email: str) -> None:
    """실패 횟수 초과 시 HTTP 423 반환. NFR-SEC-003."""
    now = time.time()
    _purge_old(email, now)
    if len(_attempts[email]) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="로그인 시도 5회 초과. 30분 후 다시 시도해주세요.",
        )


def record_failure(email: str) -> None:
    _attempts[email].append(time.time())


def clear_attempts(email: str) -> None:
    _attempts.pop(email, None)
