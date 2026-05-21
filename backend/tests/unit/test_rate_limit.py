"""유닛 테스트 — rate_limit.py (AI 생성)"""
import time

import pytest
from fastapi import HTTPException

from app.core.rate_limit import (
    _attempts,
    check_rate_limit,
    clear_attempts,
    record_failure,
)


@pytest.fixture(autouse=True)
def clean_attempts():
    """각 테스트 전후 상태 초기화"""
    _attempts.clear()
    yield
    _attempts.clear()


class TestRateLimit:
    EMAIL = "ratetest@test.com"

    def test_under_limit_passes(self):
        for _ in range(4):
            record_failure(self.EMAIL)
        check_rate_limit(self.EMAIL)  # 예외 없어야 함

    def test_over_limit_raises_423(self):
        for _ in range(5):
            record_failure(self.EMAIL)
        with pytest.raises(HTTPException) as exc:
            check_rate_limit(self.EMAIL)
        assert exc.value.status_code == 423

    def test_clear_resets_counter(self):
        for _ in range(5):
            record_failure(self.EMAIL)
        clear_attempts(self.EMAIL)
        check_rate_limit(self.EMAIL)  # 초기화 후 통과

    def test_expired_attempts_purged(self):
        """30분 이전 시도는 만료로 처리"""
        now = time.time()
        expired = now - (31 * 60)
        _attempts[self.EMAIL] = [expired] * 5  # 31분 전 5회
        check_rate_limit(self.EMAIL)  # 만료된 시도 → 통과

    def test_independent_per_email(self):
        other = "other@test.com"
        for _ in range(5):
            record_failure(self.EMAIL)
        check_rate_limit(other)  # 다른 이메일은 통과

    def test_423_detail_message(self):
        for _ in range(5):
            record_failure(self.EMAIL)
        with pytest.raises(HTTPException) as exc:
            check_rate_limit(self.EMAIL)
        assert "30분" in exc.value.detail
