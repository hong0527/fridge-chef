"""모델 A 단위 테스트 — SRS FR-011, NFR-EVAL-001, NFR-PERF-002.

- 5차원 벡터 정확성 (맵기/5, 난이도/3, 저칼로리, 국가, 테마)
- 코사인 유사도 동점 시 cook_min asc 정렬
- contains_all 하드 필터
- 알레르기 0% (NFR-EVAL-001)
- max_cook_min 초과 제외
"""

from __future__ import annotations

import math

import pytest

from app.services.model_a import (
    _cosine,
    _contains_all,
    _vec_from_prefs,
    _vec_from_recipe,
    recommend_cold_storage,
)


# ─────────────────────────────────────────────────────────────
class TestVector:
    """5차원 벡터 변환."""

    def test_vec_from_recipe_dimensions(self, recipe_repo) -> None:
        """# FR-011 — 레시피 벡터는 정확히 5차원."""
        recipe = recipe_repo.get("t001")
        vec = _vec_from_recipe(recipe)
        assert len(vec) == 5

    def test_vec_spicy_normalized_by_5(self, recipe_repo) -> None:
        """# FR-011 — 맵기 차원 = spicy/5."""
        recipe = recipe_repo.get("t002")  # spicy=2
        vec = _vec_from_recipe(recipe)
        assert math.isclose(vec[0], 2 / 5.0)

    def test_vec_difficulty_normalized_by_3(self, recipe_repo) -> None:
        """# FR-011 — 난이도 차원 = difficulty_level/3."""
        recipe = recipe_repo.get("t004")  # difficulty_level=2
        vec = _vec_from_recipe(recipe)
        assert math.isclose(vec[1], 2 / 3.0)

    def test_vec_low_calorie_binary(self, recipe_repo) -> None:
        """# FR-011 — 저칼로리 차원 = 0 or 1."""
        low = recipe_repo.get("t003")  # is_low_calorie=True
        not_low = recipe_repo.get("t002")
        assert _vec_from_recipe(low)[2] == 1.0
        assert _vec_from_recipe(not_low)[2] == 0.0

    def test_vec_country_encoded(self, recipe_repo) -> None:
        """# FR-011 — 국가 코드 인코딩 (kr=0.2, west=0.8)."""
        kr = recipe_repo.get("t001")  # country=kr
        west = recipe_repo.get("t003")  # country=west
        assert math.isclose(_vec_from_recipe(kr)[3], 0.2)
        assert math.isclose(_vec_from_recipe(west)[3], 0.8)

    def test_vec_theme_encoded(self, recipe_repo) -> None:
        """# FR-011 — 테마 코드 인코딩 (main=0.2, side=0.4)."""
        main = recipe_repo.get("t001")
        side = recipe_repo.get("t005")  # theme=side
        assert math.isclose(_vec_from_recipe(main)[4], 0.2)
        assert math.isclose(_vec_from_recipe(side)[4], 0.4)

    def test_vec_from_prefs_korean_labels(self) -> None:
        """# FR-011 — 한글 선호도 → 코드 변환."""
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
        assert math.isclose(vec[3], 0.8)        # west
        assert math.isclose(vec[4], 0.8)        # dessert


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
        """# FR-011 — 냉장고 ⊇ 레시피 → True."""
        fridge = {"두부", "간장", "마늘", "양파"}
        recipe = ["두부", "간장", "마늘"]
        assert _contains_all(fridge, recipe) is True

    def test_missing_one_ingredient_returns_false(self) -> None:
        """# FR-011 — 1개라도 부족 → False."""
        fridge = {"두부", "간장"}
        recipe = ["두부", "간장", "마늘"]
        assert _contains_all(fridge, recipe) is False


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
