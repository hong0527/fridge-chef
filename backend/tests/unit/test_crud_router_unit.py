"""favorites/fridge/recipes 라우터 함수 직접 호출 단위 테스트 — coverage 보완.

Python 3.13 + coverage.py sys.monitoring 버그 우회:
ASGI transport를 통한 호출 시 await 재개 지점의 LINE 이벤트가 발생하지 않으므로,
route 함수를 직접 호출해 coverage 추적 범위에 포함시킨다.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.api.favorites as fav_mod
import app.api.fridge as fridge_mod
import app.api.recipes as recipes_mod


def _user(user_id: str = "1") -> MagicMock:
    u = MagicMock()
    u.user_id = user_id
    return u


def _ingredient_row(
    id: int = 1,
    raw_name: str = "양파",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        raw_name=raw_name,
        normalized_name=raw_name,
        quantity=None,
        expires_at=None,
        created_at=datetime(2025, 1, 1),
    )


class TestFavoritesRouterUnit:
    """favorites.py 라우터 직접 호출 — 모든 분기 coverage."""

    async def test_list_favorites_builds_response(self, monkeypatch) -> None:
        fav = SimpleNamespace(created_at=datetime(2025, 1, 1))
        recipe = SimpleNamespace(
            recipe_id="r001",
            name="간장계란밥",
            cook_min=10,
            spicy=1,
            difficulty_level=1,
            country="kr",
            theme="main",
            image_url=None,
        )
        monkeypatch.setattr(
            fav_mod.favorites_service,
            "list_for_user",
            AsyncMock(return_value=[(fav, recipe)]),
        )

        result = await fav_mod.list_favorites(user=_user(), db=AsyncMock())

        assert result.total == 1
        assert result.items[0].recipe_id == "r001"
        assert result.items[0].name == "간장계란밥"
        assert result.items[0].cook_min == 10

    async def test_list_favorites_empty(self, monkeypatch) -> None:
        monkeypatch.setattr(
            fav_mod.favorites_service,
            "list_for_user",
            AsyncMock(return_value=[]),
        )

        result = await fav_mod.list_favorites(user=_user(), db=AsyncMock())

        assert result.total == 0
        assert result.items == []

    async def test_check_favorite_returns_true(self, monkeypatch) -> None:
        monkeypatch.setattr(
            fav_mod.favorites_service, "is_favorite", AsyncMock(return_value=True)
        )

        result = await fav_mod.check_favorite(recipe_id="r001", user=_user(), db=AsyncMock())

        assert result.is_favorite is True

    async def test_check_favorite_returns_false(self, monkeypatch) -> None:
        monkeypatch.setattr(
            fav_mod.favorites_service, "is_favorite", AsyncMock(return_value=False)
        )

        result = await fav_mod.check_favorite(recipe_id="r002", user=_user(), db=AsyncMock())

        assert result.is_favorite is False

    async def test_add_favorite_returns_message_dict(self, monkeypatch) -> None:
        monkeypatch.setattr(
            fav_mod.favorites_service, "add_favorite", AsyncMock(return_value=None)
        )

        result = await fav_mod.add_favorite(recipe_id="r001", user=_user(), db=AsyncMock())

        assert isinstance(result, dict)
        assert "message" in result

    async def test_remove_favorite_not_found_raises_404(self, monkeypatch) -> None:
        monkeypatch.setattr(
            fav_mod.favorites_service, "remove_favorite", AsyncMock(return_value=False)
        )

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await fav_mod.remove_favorite(recipe_id="r999", user=_user(), db=AsyncMock())
        assert exc.value.status_code == 404

    async def test_remove_favorite_success_returns_none(self, monkeypatch) -> None:
        monkeypatch.setattr(
            fav_mod.favorites_service, "remove_favorite", AsyncMock(return_value=True)
        )

        result = await fav_mod.remove_favorite(recipe_id="r001", user=_user(), db=AsyncMock())

        assert result is None


class TestFridgeRouterUnit:
    """fridge.py 라우터 직접 호출 — 모든 분기 coverage."""

    async def test_list_ingredients_returns_response(self, monkeypatch) -> None:
        row = _ingredient_row()
        monkeypatch.setattr(
            fridge_mod.fridge_service,
            "list_for_user",
            AsyncMock(return_value=[row]),
        )

        result = await fridge_mod.list_ingredients(user=_user(), db=AsyncMock())

        assert result.total == 1
        assert result.items[0].raw_name == "양파"
        assert result.items[0].id == 1

    async def test_list_ingredients_empty(self, monkeypatch) -> None:
        monkeypatch.setattr(
            fridge_mod.fridge_service,
            "list_for_user",
            AsyncMock(return_value=[]),
        )

        result = await fridge_mod.list_ingredients(user=_user(), db=AsyncMock())

        assert result.total == 0

    async def test_create_ingredient_returns_response(self, monkeypatch) -> None:
        row = _ingredient_row(id=7, raw_name="당근")
        monkeypatch.setattr(
            fridge_mod.fridge_service,
            "add_for_user",
            AsyncMock(return_value=row),
        )

        from app.schemas.fridge import IngredientCreate

        payload = IngredientCreate(raw_name="당근")
        result = await fridge_mod.create_ingredient(payload=payload, user=_user(), db=AsyncMock())

        assert result.raw_name == "당근"
        assert result.id == 7

    async def test_delete_ingredient_not_found_raises_404(self, monkeypatch) -> None:
        monkeypatch.setattr(
            fridge_mod.fridge_service,
            "delete_for_user",
            AsyncMock(return_value=False),
        )

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await fridge_mod.delete_ingredient(ingredient_id=99999, user=_user(), db=AsyncMock())
        assert exc.value.status_code == 404

    async def test_delete_ingredient_success_returns_none(self, monkeypatch) -> None:
        monkeypatch.setattr(
            fridge_mod.fridge_service,
            "delete_for_user",
            AsyncMock(return_value=True),
        )

        result = await fridge_mod.delete_ingredient(
            ingredient_id=1, user=_user(), db=AsyncMock()
        )

        assert result is None


class TestRecipesRouterUnit:
    """recipes.py 라우터 직접 호출 — not-found / success 분기 coverage."""

    async def test_get_recipe_not_found_raises_404(self) -> None:
        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=None)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await recipes_mod.get_recipe(recipe_id="nonexistent-id", db=mock_db)
        assert exc.value.status_code == 404

    async def test_get_recipe_success_returns_dict(self) -> None:
        mock_row = SimpleNamespace(
            recipe_id="r001",
            name="간장계란밥",
            whole_ingredients=["밥", "계란", "간장"],
            steps=["밥을 짓는다.", "계란을 부친다."],
            cook_min=10,
            spicy=1,
            difficulty_level=1,
            is_low_calorie=False,
            country="kr",
            theme="main",
            allergens=["계란"],
            image_url=None,
        )
        mock_db = AsyncMock()
        mock_db.scalar = AsyncMock(return_value=mock_row)

        result = await recipes_mod.get_recipe(recipe_id="r001", db=mock_db)

        assert result["recipe_id"] == "r001"
        assert result["name"] == "간장계란밥"
        assert "steps" in result
        assert "allergens" in result
        assert result["allergens"] == ["계란"]
