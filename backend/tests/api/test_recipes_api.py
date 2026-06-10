"""레시피 상세 API 통합 테스트 — SDD §3 UC-04.

- GET /api/recipes/{id} 단건 조회
- 응답 필드: 이름·조리시간·맵기·난이도·국가·테마·알레르기·재료·조리순서
"""

from __future__ import annotations

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def seeded_recipe(db_session):  # type: ignore[no-untyped-def]
    """DB에 단일 레시피 삽입 — recipes API 가 ORM 테이블에서 조회."""
    from app.models.orm import RecipeRow

    row = RecipeRow(
        recipe_id="uc04_recipe_001",
        name="UC04 김치찌개",
        whole_ingredients=["김치", "돼지고기", "두부", "대파"],
        steps=[
            "1. 김치를 볶는다",
            "2. 돼지고기를 넣고 함께 볶는다",
            "3. 물을 붓고 끓인다",
            "4. 두부와 대파를 넣고 마무리",
        ],
        cook_min=30,
        spicy=4,
        difficulty_level=2,
        is_low_calorie=False,
        country="kr",
        theme="soup",
        allergens=["돼지고기", "대두"],
        image_url="https://example.com/uc04.png",
    )
    db_session.add(row)
    await db_session.commit()
    return row


class TestRecipesNotFound:
    """GET /api/recipes/{recipe_id} — 404/200 경로 (AC-008~009)."""

    async def test_ac008_get_nonexistent_recipe_returns_404(
        self, async_client
    ) -> None:
        """AC-008: DB에 없는 recipe_id 조회 → 404."""
        resp = await async_client.get("/api/recipes/nonexistent-id-ac008")
        assert resp.status_code == 404

    async def test_ac009_get_existing_recipe_returns_required_fields(
        self, async_client, db_session
    ) -> None:
        """AC-009: DB에 존재하는 recipe_id 조회 → 200, recipe_id·name·steps·allergens 필드 포함."""
        from app.models.orm import RecipeRow

        row = RecipeRow(
            recipe_id="ac009-seed",
            name="AC009 테스트요리",
            whole_ingredients=["재료1", "재료2"],
            steps=["단계1", "단계2"],
            cook_min=15,
            spicy=2,
            difficulty_level=1,
            is_low_calorie=False,
            country="kr",
            theme="main",
            allergens=["밀"],
        )
        db_session.add(row)
        await db_session.commit()

        resp = await async_client.get("/api/recipes/ac009-seed")
        assert resp.status_code == 200
        body = resp.json()
        assert body["recipe_id"] == "ac009-seed"
        assert body["name"] == "AC009 테스트요리"
        assert "steps" in body
        assert "allergens" in body


class TestRecipeDetail:
    """GET /api/recipes/{id} — UC-04."""

    async def test_get_existing_recipe_returns_200(
        self, async_client, seeded_recipe
    ) -> None:
        """# UC-04 — 존재하는 레시피 → 200."""
        resp = await async_client.get(f"/api/recipes/{seeded_recipe.recipe_id}")
        assert resp.status_code == 200

    async def test_get_nonexistent_recipe_returns_404(self, async_client) -> None:
        """# UC-04 — 존재하지 않는 ID → 404."""
        resp = await async_client.get("/api/recipes/no_such_id_xyz")
        assert resp.status_code == 404

    async def test_response_contains_required_fields(
        self, async_client, seeded_recipe
    ) -> None:
        """# UC-04 — 응답 필드 검증.

        명세 필드: 이름·조리시간·맵기·난이도·저칼로리·국가·테마·알레르기·재료·조리순서.
        (사진/인분/칼로리 수치 등 추가 필드는 SDD 확장 시 보강)
        """
        resp = await async_client.get(f"/api/recipes/{seeded_recipe.recipe_id}")
        body = resp.json()
        required = {
            "recipe_id",
            "name",
            "whole_ingredients",
            "steps",
            "cook_min",
            "spicy",
            "difficulty_level",
            "is_low_calorie",
            "country",
            "theme",
            "allergens",
            "image_url",
        }
        missing = required - set(body.keys())
        assert not missing, f"UC-04 필수 필드 누락: {missing}"

    async def test_response_field_values_match_seed(
        self, async_client, seeded_recipe
    ) -> None:
        """# UC-04 — 응답 값이 DB 시드와 일치."""
        resp = await async_client.get(f"/api/recipes/{seeded_recipe.recipe_id}")
        body = resp.json()
        assert body["name"] == "UC04 김치찌개"
        assert body["cook_min"] == 30
        assert body["spicy"] == 4
        assert body["difficulty_level"] == 2
        assert body["country"] == "kr"
        assert body["theme"] == "soup"
        assert "돼지고기" in body["allergens"]
        assert len(body["steps"]) == 4, "조리순서 4단계"

    @pytest.mark.xfail(
        reason="사용자 알레르기 기반 warning 필드는 recipes 라우터 응답에 미구현 (스키마 확장 필요)",
        strict=False,
    )
    async def test_response_warns_when_user_allergic(
        self, async_client, seeded_recipe
    ) -> None:
        """# UC-04 — 사용자 알레르기와 일치 시 warning 필드 포함."""
        resp = await async_client.get(
            f"/api/recipes/{seeded_recipe.recipe_id}",
            headers={"X-User-Allergies": "돼지고기"},
        )
        body = resp.json()
        assert "warning" in body
        assert "돼지고기" in body["warning"]
