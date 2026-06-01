"""recommend_service._safe_run 단위 테스트 — RS-001~003.

타임아웃 격리 로직을 모듈 레벨에서 직접 검증한다.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.recommend_service import _safe_run


async def _ok() -> list[dict]:
    return [{"id": 1, "name": "된장찌개"}]


async def _timeout() -> list[dict]:
    await asyncio.sleep(10)
    return []


async def _raises() -> list[dict]:
    raise ValueError("DB 오류")


@pytest.mark.asyncio
async def test_rs001_success():
    """RS-001: 정상 실행 시 결과 리스트를 반환한다."""
    # NFR-PERF-003: 10초 파이프라인 내 정상 결과 반환 보장
    result = await _safe_run("test_model", _ok(), timeout_s=5.0)
    assert result == [{"id": 1, "name": "된장찌개"}]


@pytest.mark.asyncio
async def test_rs002_timeout():
    """RS-002: 타임아웃 초과 시 빈 리스트를 반환한다."""
    # NFR-PERF-003: 10초 타임아웃 강제 적용
    # NFR-REL-001: 타임아웃 감지 후 폴백(빈 리스트) 자동 전환
    result = await _safe_run("test_model", _timeout(), timeout_s=0.05)
    assert result == []


@pytest.mark.asyncio
async def test_rs003_exception():
    """RS-003: 코루틴 실행 중 예외 발생 시 빈 리스트를 반환한다."""
    # NFR-REL-001: 예외 발생 시 폴백(빈 리스트) 자동 전환 — 다른 모델 결과 폐기 방지
    result = await _safe_run("test_model", _raises(), timeout_s=5.0)
    assert result == []
