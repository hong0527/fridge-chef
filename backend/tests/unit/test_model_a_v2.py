"""모델 A 난이도 매칭 점수 테스트 (MA-NEW-001~004).

- NFR-PERF-002: 모델 A 추천 결과 정확성 (난이도 매칭 회귀 방지)

PR #38 이후 score 함수는 가중합 (Aggarwal 2016 §4.4):
  score = 0.25*country + 0.20*theme + 0.18*diff_match + 0.12*spicy_match
        + 0.10*diet_match + 0.15*cook_norm
  diff_match = 1 - |r.difficulty_level - pref| / 2

난이도 매칭 기여:
  차이=0 → diff_match=1.0 → score 기여 +0.18
  차이=1 → diff_match=0.5 → score 기여 +0.09
  차이=2 → diff_match=0.0 → score 기여 +0.00

(이전 PR #32의 diff_bonus +0.15/+0.075/0.0 공식은 PR #38에서 가중합으로 통합됨.)
"""

from __future__ import annotations

import math

import pytest

from app.core.synonym_map import normalize_list
from app.models.recipe import Recipe
from app.models.recipe_repository import RecipeRepository
from app.services.model_a import recommend_cold_storage

# 사용자 선호: 초보(1), 한식, 메인요리, 맵기1, 다이어트 비활성
_PREFS = {
    "spicy": 1,
    "difficulty": "초보",
    "max_cook_min": 60,
    "country": "한식",
    "food_type": "메인요리",
    "diet": False,
}
_FRIDGE = ["두부"]

# 가중합 기준값 (cook_norm은 cook_min=10, max_cook=60 기준 1 - 10/60 ≈ 0.833):
#   완전 일치 baseline = 0.25 + 0.20 + 0.18*diff_match + 0.12*spicy_match
#                     + 0.10*diet_match + 0.15*cook_norm
# country/theme/spicy/diet/cook 고정 → diff_match만 차이.
# spicy 완전 일치 → spicy_match=1.0 → 0.12 기여
# diet=False · is_low_calorie=False → diet_match=1.0 → 0.10 기여
_BASE_FIXED = 0.25 + 0.20 + 0.12 + 0.10 + 0.15 * (1.0 - 10 / 60)  # ≈ 0.7950


@pytest.fixture
def diff_bonus_repo() -> RecipeRepository:
    """난이도 격리용 미니 카탈로그.

    spicy/country/theme/diet/cook_min 완전 일치, difficulty_level만 1·2·3으로 다름.
    동일 재료(두부)로 contains_all 필터를 모두 통과.
    """
    ings = normalize_list(["두부"])
    return RecipeRepository([
        Recipe("db001", "초보요리", ings, cook_min=10, spicy=1,
               difficulty_level=1, country="kr", theme="main"),
        Recipe("db002", "중급요리", ings, cook_min=10, spicy=1,
               difficulty_level=2, country="kr", theme="main"),
        Recipe("db003", "고급요리", ings, cook_min=10, spicy=1,
               difficulty_level=3, country="kr", theme="main"),
    ])


def _score_for(results: list[dict], recipe_id: str) -> float:
    for item in results:
        if item["recipe_id"] == recipe_id:
            return item["score"]
    raise KeyError(f"{recipe_id} not found in results")


class TestDiffMatchContribution:
    """MA-NEW-001~003: 가중합에서 difficulty match 기여 검증 (PR #38 공식)."""

    @pytest.mark.asyncio
    async def test_ma_new_001_diff_exact_match_full_score(self, diff_bonus_repo) -> None:
        """MA-NEW-001 — 난이도 완전 일치(차이=0): diff 기여 = 0.18 (=0.18 * 1.0)."""
        out = await recommend_cold_storage(
            fridge_ingredients=_FRIDGE,
            preferences=_PREFS,
            user_allergies=[],
            repo=diff_bonus_repo,
        )
        score = _score_for(out, "db001")
        diff_contribution = score - _BASE_FIXED
        assert math.isclose(diff_contribution, 0.18, abs_tol=1e-3), (
            f"diff_match(차이=0) 기여 기대 0.18, 실제 {diff_contribution:.4f}"
        )

    @pytest.mark.asyncio
    async def test_ma_new_002_diff_one_step_half_score(self, diff_bonus_repo) -> None:
        """MA-NEW-002 — 난이도 1단계 차이: diff 기여 = 0.09 (=0.18 * 0.5)."""
        out = await recommend_cold_storage(
            fridge_ingredients=_FRIDGE,
            preferences=_PREFS,
            user_allergies=[],
            repo=diff_bonus_repo,
        )
        score = _score_for(out, "db002")
        diff_contribution = score - _BASE_FIXED
        assert math.isclose(diff_contribution, 0.09, abs_tol=1e-3), (
            f"diff_match(차이=1) 기여 기대 0.09, 실제 {diff_contribution:.4f}"
        )

    @pytest.mark.asyncio
    async def test_ma_new_003_diff_two_steps_zero_score(self, diff_bonus_repo) -> None:
        """MA-NEW-003 — 난이도 2단계 이상 차이: diff 기여 = 0.00 (=0.18 * 0.0)."""
        out = await recommend_cold_storage(
            fridge_ingredients=_FRIDGE,
            preferences=_PREFS,
            user_allergies=[],
            repo=diff_bonus_repo,
        )
        score = _score_for(out, "db003")
        diff_contribution = score - _BASE_FIXED
        assert math.isclose(diff_contribution, 0.00, abs_tol=1e-3), (
            f"diff_match(차이=2) 기여 기대 0.00, 실제 {diff_contribution:.4f}"
        )


class TestDiffBonusRanking:
    """MA-NEW-004: diff_bonus가 실제 추천 순서에 반영되는지 검증."""

    @pytest.mark.asyncio
    async def test_ma_new_004_difficulty_match_ranks_first(self, diff_bonus_repo) -> None:
        """MA-NEW-004 — 사용자 난이도와 일치하는 레시피가 상위에 위치해야 함.

        사용자 초보(1) 선호 시 예상 순위:
          db001(초보, score≈1.15) > db002(중급, score≈0.969) > db003(고급, score≈0.894)
        """
        out = await recommend_cold_storage(
            fridge_ingredients=_FRIDGE,
            preferences=_PREFS,
            user_allergies=[],
            repo=diff_bonus_repo,
        )
        ids = [item["recipe_id"] for item in out]

        assert ids[0] == "db001", (
            f"사용자 난이도(초보)와 일치하는 db001이 1위여야 함, 실제 순서: {ids}"
        )
        assert ids.index("db002") < ids.index("db003"), (
            "1단계 차이 레시피(db002)가 2단계 차이 레시피(db003)보다 상위여야 함"
        )
