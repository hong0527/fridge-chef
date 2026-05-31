"""모델 A diff_bonus 점수 계산 테스트 (MA-NEW-001~004).

- NFR-PERF-002: 모델 A 추천 결과 정확성 (diff_bonus 랭킹 로직 회귀 방지)

907de6a 커밋에서 추가된 난이도 일치 보너스 점수 회귀 방지.

공식: diff_bonus = max(0.0, 0.15 - 0.075 × |recipe.difficulty_level - pref_difficulty|)
  차이=0 → 0.15 / 차이=1 → 0.075 / 차이≥2 → 0.0
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

# 코사인 기준값
# 모든 5차원 일치(diff_match=1): cosine([1,1,1,1,1], [1,1,1,1,1]) = 1.0
_BASE_COSINE_MATCH = 1.0
# diff_match=0, 나머지 4차원 일치: cosine([1,0,1,1,1], [1,1,1,1,1]) = 4/(2*√5) = 2/√5
_BASE_COSINE_MISMATCH = 2.0 / math.sqrt(5.0)


@pytest.fixture
def diff_bonus_repo() -> RecipeRepository:
    """diff_bonus 격리용 미니 카탈로그.

    spicy/country/theme/diet 완전 일치, difficulty_level만 1·2·3으로 다름.
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


class TestDiffBonusCalculation:
    """MA-NEW-001~003: diff_bonus 수식 정확성 검증."""

    @pytest.mark.asyncio
    async def test_ma_new_001_diff_bonus_exact_match(self, diff_bonus_repo) -> None:
        """MA-NEW-001 — 난이도 완전 일치(차이=0): diff_bonus == 0.15.

        사용자 초보(1) + 레시피 초보(1): 코사인=1.0, diff_bonus=0.15 → score=1.15.
        """
        out = await recommend_cold_storage(
            fridge_ingredients=_FRIDGE,
            preferences=_PREFS,
            user_allergies=[],
            repo=diff_bonus_repo,
        )
        score = _score_for(out, "db001")
        diff_bonus = score - _BASE_COSINE_MATCH
        assert math.isclose(diff_bonus, 0.15, abs_tol=1e-3), (
            f"diff_bonus(차이=0) 기대 0.15, 실제 {diff_bonus:.4f}"
        )

    @pytest.mark.asyncio
    async def test_ma_new_002_diff_bonus_one_step(self, diff_bonus_repo) -> None:
        """MA-NEW-002 — 난이도 1단계 차이: diff_bonus == 0.075.

        사용자 초보(1) + 레시피 중급(2): 코사인=2/√5, diff_bonus=0.075.
        """
        out = await recommend_cold_storage(
            fridge_ingredients=_FRIDGE,
            preferences=_PREFS,
            user_allergies=[],
            repo=diff_bonus_repo,
        )
        score = _score_for(out, "db002")
        diff_bonus = score - _BASE_COSINE_MISMATCH
        assert math.isclose(diff_bonus, 0.075, abs_tol=1e-3), (
            f"diff_bonus(차이=1) 기대 0.075, 실제 {diff_bonus:.4f}"
        )

    @pytest.mark.asyncio
    async def test_ma_new_003_diff_bonus_two_or_more_steps(self, diff_bonus_repo) -> None:
        """MA-NEW-003 — 난이도 2단계 이상 차이: diff_bonus == 0.0.

        사용자 초보(1) + 레시피 고급(3): 코사인=2/√5, diff_bonus=max(0, 0.15-0.15)=0.0.
        """
        out = await recommend_cold_storage(
            fridge_ingredients=_FRIDGE,
            preferences=_PREFS,
            user_allergies=[],
            repo=diff_bonus_repo,
        )
        score = _score_for(out, "db003")
        diff_bonus = score - _BASE_COSINE_MISMATCH
        assert math.isclose(diff_bonus, 0.0, abs_tol=1e-3), (
            f"diff_bonus(차이≥2) 기대 0.0, 실제 {diff_bonus:.4f}"
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
