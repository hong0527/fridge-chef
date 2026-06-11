"""core/auth.py — get_current_user 의존성 단위 테스트 (AU-001).

Python 3.13 + coverage.py sys.monitoring 버그 우회:
ASGI transport 경유 시 Depends 함수의 await 재개 이후 라인(LINE 이벤트)이
누락되므로, get_current_user 를 직접 await 호출해 coverage 범위에 포함시킨다.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.auth import get_current_user
from app.core.security import create_access_token


class TestGetCurrentUserUnit:
    """get_current_user — 유효 토큰·미존재 사용자 → 401 (AU-001)."""

    async def test_au001_valid_token_unknown_user_raises_401(self, db_session) -> None:
        """AU-001 — 서명은 유효하지만 sub의 user_id가 DB에 없으면 401."""
        token = create_access_token(subject="999999")

        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=token, db=db_session)

        assert exc.value.status_code == 401
        assert "찾을 수 없습니다" in exc.value.detail
