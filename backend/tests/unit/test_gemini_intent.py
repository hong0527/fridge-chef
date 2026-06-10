"""parse_food_intent 단위 테스트 — GI-001~007.

빈 입력 조기 반환, Gemini 폴백, spicy 변환·범위 검증 경로를 커버한다.
_call_gemini_sdk 를 monkeypatch 로 교체하여 실제 네트워크 호출 없이 실행.
"""

from __future__ import annotations

import pytest

import app.services.gemini_intent as gi_mod


@pytest.mark.asyncio
class TestParseFoodIntent:
    """parse_food_intent — GI-001~007."""

    async def test_gi001_empty_string_returns_empty_source(self) -> None:
        """GI-001: 빈 문자열 입력 → source=="empty", food_query=="", spicy is None."""
        result = await gi_mod.parse_food_intent("")
        assert result == {"food_query": "", "spicy": None, "source": "empty"}

    async def test_gi002_whitespace_only_returns_empty_source(self) -> None:
        """GI-002: 공백만 있는 문자열 → strip() 후 빈 문자열 → source=="empty"."""
        result = await gi_mod.parse_food_intent("   ")
        assert result["source"] == "empty"
        assert result["food_query"] == ""
        assert result["spicy"] is None

    async def test_gi003_gemini_returns_no_food_query_fallback(
        self, monkeypatch
    ) -> None:
        """GI-003: _call_gemini_sdk 가 {} 반환 (food_query 없음) → source=="fallback", food_query 원문."""
        # NFR-REL-001 — Gemini 응답에 food_query 없을 때 폴백 자동 전환, 원문 컨텍스트 유지

        async def _empty_sdk(_: str) -> str:
            return "{}"

        monkeypatch.setattr(gi_mod, "_call_gemini_sdk", _empty_sdk)

        result = await gi_mod.parse_food_intent("오늘 짜증나")
        assert result["source"] == "fallback"
        assert result["food_query"] == "오늘 짜증나"
        assert result["spicy"] is None

    async def test_gi004_gemini_returns_none_fallback(self, monkeypatch) -> None:
        """GI-004: _call_gemini_sdk 가 None 반환 → source=="fallback", food_query 원문."""
        # NFR-REL-001 — Gemini SDK 가 None 반환(타임아웃·API 오류) 시 폴백 자동 전환

        async def _none_sdk(_: str) -> None:
            return None

        monkeypatch.setattr(gi_mod, "_call_gemini_sdk", _none_sdk)

        result = await gi_mod.parse_food_intent("오늘 짜증나")
        assert result["source"] == "fallback"
        assert result["food_query"] == "오늘 짜증나"

    async def test_gi005_spicy_valid_range_returns_spicy_and_gemini_source(
        self, monkeypatch
    ) -> None:
        """GI-005: Gemini 응답에 spicy:3 포함 (정상 범위) → spicy==3, source=="gemini"."""

        async def _ok_sdk(_: str) -> str:
            return '{"food_query": "맵고 얼큰한 음식", "spicy": 3}'

        monkeypatch.setattr(gi_mod, "_call_gemini_sdk", _ok_sdk)

        result = await gi_mod.parse_food_intent("오늘 짜증나")
        assert result["spicy"] == 3
        assert result["source"] == "gemini"
        assert "맵고" in result["food_query"]

    async def test_gi006_spicy_out_of_range_lower_returns_none(
        self, monkeypatch
    ) -> None:
        """GI-006: Gemini 응답에 spicy:0 포함 (범위 이탈 하한) → spicy is None."""

        async def _bad_spicy_low(_: str) -> str:
            return '{"food_query": "맵고 얼큰한 음식", "spicy": 0}'

        monkeypatch.setattr(gi_mod, "_call_gemini_sdk", _bad_spicy_low)

        result = await gi_mod.parse_food_intent("오늘 짜증나")
        assert result["spicy"] is None

    async def test_gi006_spicy_out_of_range_upper_returns_none(
        self, monkeypatch
    ) -> None:
        """GI-006 (상한): Gemini 응답에 spicy:6 포함 (범위 이탈 상한) → spicy is None."""

        async def _bad_spicy_high(_: str) -> str:
            return '{"food_query": "맵고 얼큰한 음식", "spicy": 6}'

        monkeypatch.setattr(gi_mod, "_call_gemini_sdk", _bad_spicy_high)

        result = await gi_mod.parse_food_intent("오늘 짜증나")
        assert result["spicy"] is None

    async def test_gi007_spicy_non_int_string_returns_none(
        self, monkeypatch
    ) -> None:
        """GI-007: Gemini 응답에 spicy:"매운" 포함 (변환 불가 문자열) → spicy is None."""

        async def _str_spicy(_: str) -> str:
            return '{"food_query": "맵고 얼큰한 음식", "spicy": "매운"}'

        monkeypatch.setattr(gi_mod, "_call_gemini_sdk", _str_spicy)

        result = await gi_mod.parse_food_intent("오늘 짜증나")
        assert result["spicy"] is None
