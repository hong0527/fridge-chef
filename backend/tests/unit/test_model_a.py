"""모델 A 단위 테스트 — SRS FR-011, NFR-EVAL-001, NFR-PERF-002.

- 5차원 벡터 정확성 (맵기/5, 난이도/3, 저칼로리, country_match, theme_match)
- 코사인 유사도 동점 시 cook_min asc 정렬
- contains_all 하드 필터 (양념 제외)
- 알레르기 0% — 카테고리 확장 포함 (NFR-EVAL-001)
- max_cook_min 초과 제외

NOTE: country/theme 차원은 동치 매칭(0|1)으로 변경됨 — ordinal 인코딩(kr=0.2 등)
거리 왜곡 결함을 architect 권고로 수정. SDD §3.2 "5차원 코사인" 텍스트는 유지.
"""

from __future__ import annotations

import math

import pytest

from app.services.model_a import (
    _contains_all,
    _cosine,
    _vec_from_prefs,
    _vec_from_recipe,
    recommend_cold_storage,
)


# ─────────────────────────────────────────────────────────────
_KR_MAIN_PREFS = {"country": "한식", "food_type": "메인요리"}
_WEST_DESSERT_PREFS = {"country": "양식", "food_type": "디저트"}


class TestVector:
    """5차원 벡터 변환 — country/theme는 prefs와 동치 매칭(0|1)."""

    def test_vec_from_recipe_dimensions(self, recipe_repo) -> None:
        """# FR-011 — 레시피 벡터는 정확히 5차원."""
        recipe = recipe_repo.get("t001")
        vec = _vec_from_recipe(recipe, _KR_MAIN_PREFS)
        assert len(vec) == 5

    def test_vec_spicy_normalized_by_5(self, recipe_repo) -> None:
        """# FR-011 — 맵기 차원 = spicy/5."""
        recipe = recipe_repo.get("t002")  # spicy=2
        vec = _vec_from_recipe(recipe, _KR_MAIN_PREFS)
        assert math.isclose(vec[0], 2 / 5.0)

    def test_vec_difficulty_normalized_by_3(self, recipe_repo) -> None:
        """# FR-011 — 난이도 차원 = difficulty_level/3."""
        recipe = recipe_repo.get("t004")  # difficulty_level=2
        vec = _vec_from_recipe(recipe, _KR_MAIN_PREFS)
        assert math.isclose(vec[1], 2 / 3.0)

    def test_vec_low_calorie_binary(self, recipe_repo) -> None:
        """# FR-011 — 저칼로리 차원 = 0 or 1."""
        low = recipe_repo.get("t003")  # is_low_calorie=True
        not_low = recipe_repo.get("t002")
        assert _vec_from_recipe(low, _KR_MAIN_PREFS)[2] == 1.0
        assert _vec_from_recipe(not_low, _KR_MAIN_PREFS)[2] == 0.0

    def test_vec_country_match_with_korean_prefs(self, recipe_repo) -> None:
        """# FR-011 — country 동치 매칭: 한식 선호 + 한식 레시피 → 1.0, 양식 레시피 → 0.0."""
        kr = recipe_repo.get("t001")     # country=kr
        west = recipe_repo.get("t003")    # country=west
        assert _vec_from_recipe(kr, _KR_MAIN_PREFS)[3] == 1.0
        assert _vec_from_recipe(west, _KR_MAIN_PREFS)[3] == 0.0

    def test_vec_theme_match_with_main_prefs(self, recipe_repo) -> None:
        """# FR-011 — theme 동치 매칭: 메인요리 선호 + 메인 레시피 → 1.0, 반찬 → 0.0."""
        main = recipe_repo.get("t001")    # theme=main
        side = recipe_repo.get("t005")    # theme=side
        assert _vec_from_recipe(main, _KR_MAIN_PREFS)[4] == 1.0
        assert _vec_from_recipe(side, _KR_MAIN_PREFS)[4] == 0.0

    def test_vec_country_match_inverts_with_western_prefs(self, recipe_repo) -> None:
        """# FR-011 — 양식 선호로 바꾸면 동치 결과가 반대로 바뀜 (ordinal 결함 없음 회귀)."""
        kr = recipe_repo.get("t001")
        west = recipe_repo.get("t003")
        # 양식 선호: 한식 레시피 → 0.0, 양식 레시피 → 1.0
        assert _vec_from_recipe(kr, _WEST_DESSERT_PREFS)[3] == 0.0
        assert _vec_from_recipe(west, _WEST_DESSERT_PREFS)[3] == 1.0

    def test_vec_from_prefs_country_theme_always_one(self) -> None:
        """# FR-011 — prefs 벡터의 country/theme는 자기 동치이므로 항상 1.0."""
        prefs = {
            "spicy": 5,
            "difficulty": "고급",
            "diet": True,
            "country": "양식",
            "food_type": "디저트",
        }
        vec = _vec_from_prefs(prefs)
        assert math.isclose(vec[0], 1.0)        # 5/5
        assert math.isclose(vec[1], 1.0)        # 3/3
        assert vec[2] == 1.0                    # diet
        assert vec[3] == 1.0                    # country_match (self)
        assert vec[4] == 1.0                    # theme_match (self)


# ─────────────────────────────────────────────────────────────
class TestCosine:
    """코사인 유사도."""

    def test_identical_vectors_yield_one(self) -> None:
        """# FR-011 — 동일 벡터 → 유사도 1.0."""
        v = [0.5, 0.3, 1.0, 0.2, 0.4]
        assert math.isclose(_cosine(v, v), 1.0)

    def test_zero_vector_yields_zero(self) -> None:
        """# FR-011 — 영벡터 안전 처리 (ZeroDivision 회피)."""
        assert _cosine([0, 0, 0, 0, 0], [1, 1, 1, 1, 1]) == 0.0


# ─────────────────────────────────────────────────────────────
class TestContainsAll:
    """하드 필터 — contains_all_ingredients."""

    def test_fridge_contains_all_recipe_ingredients(self) -> None:
        """# FR-011 — 냉장고 ⊇ 레시피 주재료 → True (양념 제외)."""
        fridge = {"두부", "마늘", "양파"}
        # 간장은 BASIC_SEASONINGS이므로 냉장고에 없어도 통과
        recipe = ["두부", "간장", "마늘"]
        assert _contains_all(fridge, recipe) is True

    def test_missing_one_main_ingredient_returns_false(self) -> None:
        """# FR-011 — 주재료 1개라도 부족 → False."""
        fridge = {"두부", "간장"}
        recipe = ["두부", "간장", "마늘"]  # 마늘은 주재료
        assert _contains_all(fridge, recipe) is False

    def test_seasonings_excluded_from_check(self) -> None:
        """# FR-011 회귀 — 양념(소금/식용유)만 부족해도 통과해야 함."""
        fridge = {"계란", "대파"}
        recipe = ["계란", "대파", "소금"]  # 소금은 양념
        assert _contains_all(fridge, recipe) is True


# ─────────────────────────────────────────────────────────────
class TestRecommendIntegration:
    """recommend_cold_storage end-to-end with mini repo."""

    @pytest.mark.asyncio
    async def test_hard_filter_excludes_uncovered(self, recipe_repo) -> None:
        """# FR-011 — 냉장고에 없는 재료가 1개라도 있으면 제외."""
        out = await recommend_cold_storage(
            fridge_ingredients=["두부", "간장", "마늘"],
            preferences={"spicy": 2, "difficulty": "초보", "max_cook_min": 60,
                         "country": "한식", "food_type": "메인요리"},
            user_allergies=[],
            repo=recipe_repo,
        )
        rids = {r["recipe_id"] for r in out}
        assert "t002" in rids, "t002(두부조림): 두부+간장+마늘 보유"
        assert "t001" not in rids, "t001: 밥/계란 부족"
        assert "t004" not in rids, "t004: 면/치즈 부족"

    @pytest.mark.asyncio
    async def test_max_cook_min_filter_excludes_long_recipes(self, recipe_repo) -> None:
        """# FR-011 — max_cook_min 초과 레시피 제외."""
        out = await recommend_cold_storage(
            fridge_ingredients=["두부", "간장", "마늘"],
            preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 15,
                         "country": "한식", "food_type": "메인요리"},
            user_allergies=[],
            repo=recipe_repo,
        )
        rids = {r["recipe_id"] for r in out}
        # t002 cook_min=20 > 15 → 제외
        assert "t002" not in rids

    @pytest.mark.asyncio
    async def test_allergy_zero_exposure(self, recipe_repo) -> None:
        """# NFR-EVAL-001 — 알레르기 노출 0%."""
        out = await recommend_cold_storage(
            fridge_ingredients=["밥", "계란", "간장"],
            preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                         "country": "한식", "food_type": "메인요리"},
            user_allergies=["계란"],
            repo=recipe_repo,
        )
        for item in out:
            rec = recipe_repo.get(item["recipe_id"])
            assert "계란" not in rec.allergens

    @pytest.mark.asyncio
    async def test_tie_break_by_cook_min_ascending(self, recipe_repo) -> None:
        """# FR-011 — 코사인 유사도 동점 시 cook_min asc 정렬."""
        # 동일 한식·메인·맵기 1 → 점수 동일 가능성 높음
        out = await recommend_cold_storage(
            fridge_ingredients=["밥", "계란", "간장", "두부", "마늘"],
            preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                         "country": "한식", "food_type": "메인요리"},
            user_allergies=[],
            repo=recipe_repo,
        )
        # 점수 desc, cook_min asc 검증
        for i in range(len(out) - 1):
            cur, nxt = out[i], out[i + 1]
            if math.isclose(cur["score"], nxt["score"]):
                assert cur["cook_min"] <= nxt["cook_min"], (
                    "동점 시 cook_min asc 정렬 위반"
                )

    @pytest.mark.asyncio
    async def test_golden_set_50_samples_allergy_zero(self, recipe_repo) -> None:
        """# NFR-EVAL-001 — 50샘플 골든셋 회귀 (현재 10건 채움, 40건 TODO)."""
        import json
        from pathlib import Path

        fixture_path = (
            Path(__file__).resolve().parents[1] / "fixtures" / "allergy_golden_set.json"
        )
        with fixture_path.open("r", encoding="utf-8") as f:
            samples = json.load(f)

        from app.core.synonym_map import normalize_list

        for sample in samples:
            out = await recommend_cold_storage(
                fridge_ingredients=sample["fridge"],
                preferences={
                    "spicy": sample.get("preferences", {}).get("spicy", 1),
                    "difficulty": "초보",
                    "max_cook_min": 60,
                    "country": "한식",
                    "food_type": "메인요리",
                },
                user_allergies=sample["allergies"],
                repo=recipe_repo,
            )
            forbidden = set(normalize_list(sample["allergies"]))
            for item in out:
                rec = recipe_repo.get(item["recipe_id"])
                assert not (set(rec.allergens) & forbidden), (
                    f"sample={sample}: {item['recipe_id']} allergens={rec.allergens}"
                )
