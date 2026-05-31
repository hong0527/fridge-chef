"""image_url 필드 전파 테스트 — IU-001~003 (b4da656 회귀 방지).

Recipe.to_brief_dict() 및 recommend_cold_storage 추천 응답까지
image_url 값이 올바르게 전달되는지 확인한다.

NFR 추적:
  NFR-USE-002  — IU-001·002: to_brief_dict()에 image_url 키가 없으면 레시피 목록
                 화면이 깨져 PC·태블릿 해상도에서 핵심 UC(UC-01~06) 수행 불가.
  NFR-PERF-002 — IU-003: recommend_cold_storage(모델 A) 응답이 image_url을 포함해야
                 클라이언트가 3초 이내 응답을 완전한 데이터로 처리할 수 있음.

커버리지:
  IU-001  image_url=None  → to_brief_dict()에 키 존재, 값 None
  IU-002  image_url=URL   → to_brief_dict()에 URL 그대로 반환
  IU-003  추천 응답 전체  → 모든 아이템에 image_url 키 존재
"""

from __future__ import annotations

import pytest

from app.models.recipe import Recipe
from app.models.recipe_repository import RecipeRepository
from app.services.model_a import recommend_cold_storage

_SAMPLE_URL = "https://cdn.example.com/recipe/kimchi.jpg"


class TestImageUrlPropagation:
    """IU-001~003: image_url 필드 전파."""

    def test_IU001_brief_dict_image_url_none(self) -> None:
        """IU-001 — image_url=None 레시피: 키 존재하고 값은 None.  # NFR-USE-002

        키가 없는 것과 None인 것은 다르다 — 프론트엔드가 안전하게 분기하려면
        키가 항상 포함되어야 한다.
        """
        recipe = Recipe(
            recipe_id="iu001",
            name="이미지 없는 레시피",
            whole_ingredients=["두부"],
            image_url=None,
        )
        d = recipe.to_brief_dict()
        assert "image_url" in d, "image_url 키가 응답에 없음"
        assert d["image_url"] is None

    def test_IU002_brief_dict_image_url_returned_as_is(self) -> None:
        """IU-002 — image_url URL 있는 레시피: URL이 그대로 반환됨.  # NFR-USE-002"""
        recipe = Recipe(
            recipe_id="iu002",
            name="김치찌개",
            whole_ingredients=["김치"],
            image_url=_SAMPLE_URL,
        )
        d = recipe.to_brief_dict()
        assert d.get("image_url") == _SAMPLE_URL

    @pytest.mark.asyncio
    async def test_IU003_recommend_response_contains_image_url_for_all_items(self) -> None:
        """IU-003 — 추천 응답 전체: 모든 아이템에 image_url 키 존재.  # NFR-PERF-002

        recommend_cold_storage → to_brief_dict() 경로에서 image_url이
        최종 응답 dict까지 누락 없이 전달되는지 확인한다.
        """
        repo = RecipeRepository([
            Recipe(
                recipe_id="iu003a",
                name="두부조림",
                whole_ingredients=["두부", "간장"],
                cook_min=15,
                spicy=1,
                difficulty_level=1,
                country="kr",
                theme="main",
                image_url=_SAMPLE_URL,
            ),
            Recipe(
                recipe_id="iu003b",
                name="이미지없는두부볶음",
                whole_ingredients=["두부", "간장"],
                cook_min=10,
                spicy=1,
                difficulty_level=1,
                country="kr",
                theme="main",
                image_url=None,
            ),
        ])

        out = await recommend_cold_storage(
            fridge_ingredients=["두부", "간장"],
            preferences={
                "spicy": 1,
                "difficulty": "초보",
                "max_cook_min": 60,
                "country": "한식",
                "food_type": "메인요리",
            },
            user_allergies=[],
            repo=repo,
        )

        assert len(out) > 0, "추천 결과가 비어 있음 — 필터 조건을 확인하라"
        for item in out:
            assert "image_url" in item, (
                f"{item['recipe_id']}: 추천 응답에 image_url 키 없음"
            )
