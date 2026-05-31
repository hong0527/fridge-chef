"""모델 A 난이도 매칭 회귀 테스트 (MA-NEW-001~004).

- NFR-PERF-002: 모델 A 추천 결과 정확성 (난이도 매칭 회귀 방지)

PR #40 score 함수 가중합 + Stratified 도입 후:
  score = 0.30*overlap + 0.20*country + 0.15*theme + 0.13*diff_match
        + 0.10*spicy_match + 0.07*diet_match + 0.05*cook_norm + jitter
  diff_match = 1 - |r.difficulty_level - pref| / 2

차이별 diff 기여:
  차이=0 → diff_match=1.0 → +0.13
  차이=1 → diff_match=0.5 → +0.065
  차이=2 → diff_match=0.0 → +0.0
"""

from __future__ import annotations

import pytest

from app.core.synonym_map import normalize_list
from app.models.recipe import Recipe
from app.models.recipe_repository import RecipeRepository
from app.services.model_a import recommend_cold_storage

_PREFS = {
    "spicy": 1,
    "difficulty": "초보",
    "max_cook_min": 60,
    "country": "한식",
    "food_type": "메인요리",
    "diet": False,
}
_FRIDGE = ["두부"]


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


class TestDiffMatchRanking:
    """MA-NEW-001~003: 가중합에서 난이도 차이가 score에 미치는 기여 검증.

    PR #40 stratified 도입으로 같은 country+theme 풀이면 모든 후보가 동일 tier에
    포함되어 score 비교 가능. 절대 점수가 아닌 *차이*를 검증해 가중치 튜닝에도
    안정적인 테스트.
    """

    @pytest.mark.asyncio
    async def test_ma_new_001_exact_match_score_is_highest(self, diff_bonus_repo) -> None:
        """MA-NEW-001 — 난이도 일치(db001)가 1단계 차이(db002)보다 점수 높음."""
        out = await recommend_cold_storage(
            fridge_ingredients=_FRIDGE,
            preferences=_PREFS,
            user_allergies=[],
            repo=diff_bonus_repo,
        )
        s1 = _score_for(out, "db001")  # diff_match=1.0
        s2 = _score_for(out, "db002")  # diff_match=0.5
        assert s1 > s2, f"초보 일치 score {s1} ≤ 1단계 차이 score {s2}"
        # 0.13 * (1.0 - 0.5) = 0.065 차이 기대 (jitter ±0.001 허용)
        delta = s1 - s2
        assert 0.05 < delta < 0.08, f"기대 차이 ≈ 0.065, 실제 {delta:.4f}"

    @pytest.mark.asyncio
    async def test_ma_new_002_one_step_better_than_two(self, diff_bonus_repo) -> None:
        """MA-NEW-002 — 1단계 차이(db002)가 2단계 차이(db003)보다 점수 높음."""
        out = await recommend_cold_storage(
            fridge_ingredients=_FRIDGE,
            preferences=_PREFS,
            user_allergies=[],
            repo=diff_bonus_repo,
        )
        s2 = _score_for(out, "db002")
        s3 = _score_for(out, "db003")
        assert s2 > s3, f"1단계 차이 score {s2} ≤ 2단계 차이 score {s3}"
        delta = s2 - s3
        assert 0.05 < delta < 0.08, f"기대 차이 ≈ 0.065, 실제 {delta:.4f}"

    @pytest.mark.asyncio
    async def test_ma_new_003_diff_contribution_total(self, diff_bonus_repo) -> None:
        """MA-NEW-003 — 일치 vs 2단계 차이 score 차이 ≈ 0.13 (diff 가중치 전체)."""
        out = await recommend_cold_storage(
            fridge_ingredients=_FRIDGE,
            preferences=_PREFS,
            user_allergies=[],
            repo=diff_bonus_repo,
        )
        s1 = _score_for(out, "db001")
        s3 = _score_for(out, "db003")
        delta = s1 - s3
        assert 0.12 < delta < 0.15, f"기대 차이 ≈ 0.13, 실제 {delta:.4f}"


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
