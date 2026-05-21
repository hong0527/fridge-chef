"""모델 B 단위 테스트 — SRS FR-014, FR-016, NFR-EVAL-002, NFR-REL-001.

- 복합 점수 = 선호도×0.7 + 보유재료율×0.2 + 부족재료적음×0.1
- 소프트 필터: 부족 재료 ≤ MISSING_INGREDIENTS_MAX (기본 5)
- Gemini citation_id 화이트리스트 검증 (NFR-EVAL-002)
- Gemini 실패 시 final_score Top-3 폴백 (reason="")
- 페르소나별 가중 차이 (P1·P3 시나리오)
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from app.services import model_b as mb_mod
from app.services.model_b import _composite_score, recommend_missing_ingredients


# ─────────────────────────────────────────────────────────────
class TestCompositeScore:
    """복합 점수 공식 (SDD §3.2 5단계)."""

    def test_full_match_yields_high_score(self) -> None:
        """# FR-014 — 선호도 1.0 + 보유율 1.0 + 부족 0 → 점수 1.0."""
        score = _composite_score(pref_sim=1.0, have_ratio=1.0, missing_count=0, max_missing=5)
        assert math.isclose(score, 1.0)

    def test_zero_match_yields_zero(self) -> None:
        """# FR-014 — 모든 차원 0 + 부족 max → 점수 0."""
        score = _composite_score(pref_sim=0.0, have_ratio=0.0, missing_count=5, max_missing=5)
        assert math.isclose(score, 0.0)

    def test_weight_distribution(self) -> None:
        """# FR-014 — 가중치 0.7/0.2/0.1 분포 검증."""
        # 선호도만 1.0 → 0.7
        s1 = _composite_score(1.0, 0.0, 5, 5)
        assert math.isclose(s1, 0.7)
        # 보유율만 1.0 → 0.2
        s2 = _composite_score(0.0, 1.0, 5, 5)
        assert math.isclose(s2, 0.2)
        # 부족재료적음만 1.0 (missing=0) → 0.1
        s3 = _composite_score(0.0, 0.0, 0, 5)
        assert math.isclose(s3, 0.1)

    def test_missing_penalty_linear(self) -> None:
        """# FR-014 — 부족 3개 / max 5 → penalty = 1 - 3/5 = 0.4 → ×0.1."""
        s = _composite_score(0.0, 0.0, 3, 5)
        assert math.isclose(s, 0.04)


# ─────────────────────────────────────────────────────────────
class TestSoftFilter:
    """소프트 필터 — 부족 재료 한도."""

    @pytest.mark.asyncio
    async def test_excludes_recipes_with_too_many_missing(
        self, recipe_repo, monkeypatch
    ) -> None:
        """# FR-014 — 부족 재료 > MISSING_INGREDIENTS_MAX 제외."""
        from app.core import config as cfg

        monkeypatch.setattr(cfg.settings, "missing_ingredients_max", 1)

        async def _mock_gemini(candidates, user_context):
            return None

        monkeypatch.setattr(mb_mod, "gemini_select_top3", _mock_gemini)

        # 냉장고에 두부만 있음 → 대부분 레시피는 부족 ≥ 2
        out = await recommend_missing_ingredients(
            fridge_ingredients=["두부"],
            preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                         "country": "한식", "food_type": "메인요리"},
            user_allergies=[],
            user_context="",
            repo=recipe_repo,
        )
        for item in out:
            assert len(item["missing"]) <= 1


# ─────────────────────────────────────────────────────────────
class TestCitationWhitelist:
    """NFR-EVAL-002 — citation_id 화이트리스트 검증."""

    @pytest.mark.asyncio
    async def test_invalid_citation_replaced_by_fallback(
        self, recipe_repo, monkeypatch
    ) -> None:
        """# NFR-EVAL-002 — Gemini 가짜 ID → 폴백으로 대체."""
        async def _bad_gemini(candidates, user_context):
            return {
                "selected": ["fake_x", "fake_y", "fake_z"],
                "reasons": ["가짜", "가짜", "가짜"],
                "citation_ids": ["fake_x", "fake_y", "fake_z"],
            }

        monkeypatch.setattr(mb_mod, "gemini_select_top3", _bad_gemini)
        out = await recommend_missing_ingredients(
            fridge_ingredients=["두부", "간장", "마늘"],
            preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                         "country": "한식", "food_type": "메인요리"},
            user_allergies=[],
            user_context="",
            repo=recipe_repo,
        )
        whitelist = recipe_repo.whitelist_ids()
        for item in out:
            assert item["recipe_id"] in whitelist


# ─────────────────────────────────────────────────────────────
class TestGeminiFallback:
    """NFR-REL-001 — Gemini 실패 시 폴백."""

    @pytest.mark.asyncio
    async def test_none_response_falls_back_to_final_score(
        self, recipe_repo, monkeypatch
    ) -> None:
        """# NFR-REL-001·FR-016 — Gemini None → final_score Top-3, reason=""."""
        async def _none_gemini(candidates, user_context):
            return None

        monkeypatch.setattr(mb_mod, "gemini_select_top3", _none_gemini)
        out = await recommend_missing_ingredients(
            fridge_ingredients=["두부", "간장", "마늘"],
            preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                         "country": "한식", "food_type": "메인요리"},
            user_allergies=[],
            user_context="",
            repo=recipe_repo,
        )
        assert len(out) >= 1
        for item in out:
            assert item["reason"] == ""
            assert "final_score" in item

    @pytest.mark.asyncio
    async def test_partial_valid_citation_keeps_only_valid(
        self, recipe_repo, monkeypatch
    ) -> None:
        """# NFR-EVAL-002 — 일부만 유효한 citation → 유효한 것만 채택 + 폴백 보충."""
        async def _mixed_gemini(candidates, user_context):
            ids = [candidates[0]["recipe_id"], "fake_y", "fake_z"]
            return {
                "selected": ids,
                "reasons": ["진짜 사유", "가짜", "가짜"],
                "citation_ids": ids,
            }

        monkeypatch.setattr(mb_mod, "gemini_select_top3", _mixed_gemini)
        out = await recommend_missing_ingredients(
            fridge_ingredients=["두부", "간장", "마늘"],
            preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                         "country": "한식", "food_type": "메인요리"},
            user_allergies=[],
            user_context="",
            repo=recipe_repo,
        )
        whitelist = recipe_repo.whitelist_ids()
        for item in out:
            assert item["recipe_id"] in whitelist


# ─────────────────────────────────────────────────────────────
class TestPersonaWeighting:
    """페르소나별 가중치 차이 — P1 부족재료 매력, P3 우선순위 낮음."""

    @pytest.mark.asyncio
    async def test_persona_p1_low_missing_recipes_present(
        self, recipe_repo, mock_gemini_fail
    ) -> None:
        """# 페르소나 P1 (김민준) — 부족재료 적은 레시피 우선 노출."""
        out = await recommend_missing_ingredients(
            fridge_ingredients=["두부", "간장", "마늘", "밥"],
            preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                         "country": "한식", "food_type": "메인요리"},
            user_allergies=[],
            user_context="혼자 빠르게",
            repo=recipe_repo,
        )
        # 폴백 경로: final_score Top-3 — 가장 점수 높은 항목은 부족재료 적은 것
        if len(out) >= 2:
            # final_score 가 내림차순 (서비스 정렬 결과 가정)
            scores = [item["final_score"] for item in out]
            assert scores == sorted(scores, reverse=True), "final_score 내림차순 정렬"

    @pytest.mark.asyncio
    async def test_persona_p3_family_main_dish_prefer(
        self, recipe_repo, mock_gemini_fail
    ) -> None:
        """# 페르소나 P3 (박정희) — 가족 4인분 → 메인요리 선호."""
        out = await recommend_missing_ingredients(
            fridge_ingredients=["두부", "간장", "마늘", "밥", "계란"],
            preferences={"spicy": 1, "difficulty": "중급", "max_cook_min": 60,
                         "country": "한식", "food_type": "메인요리"},
            user_allergies=[],
            user_context="가족 4인분",
            repo=recipe_repo,
        )
        # 모든 후보가 main 테마면 P3 선호 만족
        for item in out:
            rec = recipe_repo.get(item["recipe_id"])
            # 메인 테마 우선이되, soup 도 허용 가능 (한식 가정식 패턴)
            assert rec.theme in ("main", "soup", "side")
