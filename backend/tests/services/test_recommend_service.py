"""recommend_service NL intent 풍부화·폴백·예외 경로 단위 테스트 — RS-001~006.

recommend_dual 의 모델 A/B 호출과 parse_food_intent 를 monkeypatch 로 교체하여
실제 TF-IDF 연산·DB 없이 분기 경로를 검증한다.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.config import settings
from app.models.recipe_repository import RecipeRepository
from app.services import recommend_service


@pytest.mark.asyncio
class TestRecommendDualNLIntent:
    """recommend_dual NL intent 풍부화 분기 — RS-001~006."""

    async def test_rs001_nl_enrichment_appends_food_query_to_context(
        self, monkeypatch
    ) -> None:
        """RS-001: Gemini source=="gemini" + food_query 반환 → model_a 호출 시 user_context에 번역 텍스트 포함."""
        captured: dict = {}

        async def _mock_intent(_: str) -> dict:
            return {"food_query": "맵고 얼큰한 음식", "spicy": 4, "source": "gemini"}

        async def _mock_a(*, user_context, **_) -> list:
            captured["ctx"] = user_context
            return []

        async def _mock_b(**_) -> list:
            return []

        monkeypatch.setattr("app.services.gemini_intent.parse_food_intent", _mock_intent)
        monkeypatch.setattr(recommend_service, "recommend_cold_storage", _mock_a)
        monkeypatch.setattr(recommend_service, "recommend_missing_ingredients", _mock_b)
        monkeypatch.setattr(
            recommend_service, "settings",
            replace(settings, nl_intent_enabled=True, gemini_timeout_s=5.0),
        )

        await recommend_service.recommend_dual(
            fridge_ingredients=["두부"],
            preferences={"spicy": 3},
            user_allergies=[],
            user_context="오늘 짜증나",
            repo=RecipeRepository([]),
        )
        assert "맵고 얼큰한 음식" in captured["ctx"]
        assert "오늘 짜증나" in captured["ctx"]

    async def test_rs002_nl_enrichment_updates_spicy_when_default(
        self, monkeypatch
    ) -> None:
        """RS-002: Gemini spicy=4, 기본 선호 {"spicy":3} → model_a 호출 시 preferences["spicy"]==4."""
        captured: dict = {}

        async def _mock_intent(_: str) -> dict:
            return {"food_query": "맵고 얼큰한 음식", "spicy": 4, "source": "gemini"}

        async def _mock_a(*, preferences, **_) -> list:
            captured["prefs"] = preferences
            return []

        async def _mock_b(**_) -> list:
            return []

        monkeypatch.setattr("app.services.gemini_intent.parse_food_intent", _mock_intent)
        monkeypatch.setattr(recommend_service, "recommend_cold_storage", _mock_a)
        monkeypatch.setattr(recommend_service, "recommend_missing_ingredients", _mock_b)
        monkeypatch.setattr(
            recommend_service, "settings",
            replace(settings, nl_intent_enabled=True, gemini_timeout_s=5.0),
        )

        await recommend_service.recommend_dual(
            fridge_ingredients=[],
            preferences={"spicy": 3},
            user_allergies=[],
            user_context="오늘 짜증나",
            repo=RecipeRepository([]),
        )
        assert captured["prefs"]["spicy"] == 4

    async def test_rs003_nl_enrichment_preserves_explicit_spicy(
        self, monkeypatch
    ) -> None:
        """RS-003: Gemini spicy=5, 명시 선호 {"spicy":1} → model_a 호출 시 preferences["spicy"]==1 (사용자 명시값 보존)."""
        captured: dict = {}

        async def _mock_intent(_: str) -> dict:
            return {"food_query": "맵고 얼큰", "spicy": 5, "source": "gemini"}

        async def _mock_a(*, preferences, **_) -> list:
            captured["prefs"] = preferences
            return []

        async def _mock_b(**_) -> list:
            return []

        monkeypatch.setattr("app.services.gemini_intent.parse_food_intent", _mock_intent)
        monkeypatch.setattr(recommend_service, "recommend_cold_storage", _mock_a)
        monkeypatch.setattr(recommend_service, "recommend_missing_ingredients", _mock_b)
        monkeypatch.setattr(
            recommend_service, "settings",
            replace(settings, nl_intent_enabled=True, gemini_timeout_s=5.0),
        )

        await recommend_service.recommend_dual(
            fridge_ingredients=[],
            preferences={"spicy": 1},
            user_allergies=[],
            user_context="짜증나",
            repo=RecipeRepository([]),
        )
        assert captured["prefs"]["spicy"] == 1

    async def test_rs004_nl_fallback_source_keeps_original_context(
        self, monkeypatch
    ) -> None:
        """RS-004: Gemini source=="fallback" → effective_context == user_context (원문 그대로)."""
        # NFR-REL-001 — Gemini 폴백 시 원문 컨텍스트 유지, 추천 파이프라인 중단 없음
        captured: dict = {}

        async def _mock_intent(_: str) -> dict:
            return {"food_query": "짜증나", "spicy": None, "source": "fallback"}

        async def _mock_a(*, user_context, **_) -> list:
            captured["ctx"] = user_context
            return []

        async def _mock_b(**_) -> list:
            return []

        monkeypatch.setattr("app.services.gemini_intent.parse_food_intent", _mock_intent)
        monkeypatch.setattr(recommend_service, "recommend_cold_storage", _mock_a)
        monkeypatch.setattr(recommend_service, "recommend_missing_ingredients", _mock_b)
        monkeypatch.setattr(
            recommend_service, "settings",
            replace(settings, nl_intent_enabled=True, gemini_timeout_s=5.0),
        )

        await recommend_service.recommend_dual(
            fridge_ingredients=[],
            preferences={},
            user_allergies=[],
            user_context="짜증나",
            repo=RecipeRepository([]),
        )
        assert captured["ctx"] == "짜증나"

    async def test_rs005_parse_food_intent_exception_fallback(
        self, monkeypatch
    ) -> None:
        """RS-005: parse_food_intent 가 Exception 발생 → 예외 묵살, effective_context == user_context."""
        # NFR-REL-001 — Gemini 예외 발생 시 폴백 자동 전환, 파이프라인 중단 없음
        captured: dict = {}

        async def _error_intent(_: str) -> dict:
            raise RuntimeError("Gemini 네트워크 오류")

        async def _mock_a(*, user_context, **_) -> list:
            captured["ctx"] = user_context
            return []

        async def _mock_b(**_) -> list:
            return []

        monkeypatch.setattr("app.services.gemini_intent.parse_food_intent", _error_intent)
        monkeypatch.setattr(recommend_service, "recommend_cold_storage", _mock_a)
        monkeypatch.setattr(recommend_service, "recommend_missing_ingredients", _mock_b)
        monkeypatch.setattr(
            recommend_service, "settings",
            replace(settings, nl_intent_enabled=True, gemini_timeout_s=5.0),
        )

        result = await recommend_service.recommend_dual(
            fridge_ingredients=[],
            preferences={},
            user_allergies=[],
            user_context="짜증나",
            repo=RecipeRepository([]),
        )
        assert captured["ctx"] == "짜증나"
        assert "model_a" in result

    async def test_rs006_nl_intent_disabled_skips_parse(
        self, monkeypatch
    ) -> None:
        """RS-006: nl_intent_enabled=False → parse_food_intent 미호출, model_a·model_b 정상 실행."""
        call_count = {"intent": 0, "a": 0, "b": 0}

        async def _should_not_call(_: str) -> dict:
            call_count["intent"] += 1
            return {"food_query": "unused", "spicy": None, "source": "gemini"}

        async def _mock_a(**_) -> list:
            call_count["a"] += 1
            return []

        async def _mock_b(**_) -> list:
            call_count["b"] += 1
            return []

        monkeypatch.setattr("app.services.gemini_intent.parse_food_intent", _should_not_call)
        monkeypatch.setattr(recommend_service, "recommend_cold_storage", _mock_a)
        monkeypatch.setattr(recommend_service, "recommend_missing_ingredients", _mock_b)
        monkeypatch.setattr(
            recommend_service, "settings",
            replace(settings, nl_intent_enabled=False),
        )

        result = await recommend_service.recommend_dual(
            fridge_ingredients=["두부"],
            preferences={},
            user_allergies=[],
            user_context="오늘 짜증나",
            repo=RecipeRepository([]),
        )
        assert call_count["intent"] == 0
        assert call_count["a"] == 1
        assert call_count["b"] == 1
        assert "model_a" in result and "model_b" in result
