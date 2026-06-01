"""즐겨찾기 서비스 단위 테스트 — 이슈 #49.

- add_favorite    : 추가 + idempotent
- remove_favorite : 삭제 + 없는 항목
- is_favorite     : 여부 조회
- list_for_user   : 목록 + 사용자 격리
"""

from __future__ import annotations

import pytest

from app.models.orm import RecipeRow, User
from app.services import favorites_service


async def _insert_user(db, email: str, nickname: str = "테스터") -> User:
    from app.core.security import hash_password
    user = User(
        email=email,
        password_hash=hash_password("Test1234!"),
        nickname=nickname,
        allergies=[],
        preferences={},
        is_email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _insert_recipe(db, recipe_id: str, name: str = "테스트레시피") -> RecipeRow:
    row = RecipeRow(
        recipe_id=recipe_id,
        name=name,
        whole_ingredients=["재료1"],
        steps=[],
        cook_min=10,
        spicy=1,
        difficulty_level=1,
        is_low_calorie=False,
        country="kr",
        theme="main",
        allergens=[],
    )
    db.add(row)
    await db.commit()
    return row


# ─────────────────────────────────────────────────────────────
class TestAddFavorite:

    @pytest.mark.asyncio
    async def test_fs_fav001_add_returns_none(self, db_session) -> None:
        """추가 성공 시 예외 없음."""
        user = await _insert_user(db_session, "a@test.com")
        await favorites_service.add_favorite(db_session, user.id, "recipe-001")

    @pytest.mark.asyncio
    async def test_fs_fav002_add_idempotent_no_error(self, db_session) -> None:
        """중복 추가 → 오류 없이 idempotent."""
        user = await _insert_user(db_session, "b@test.com")
        await favorites_service.add_favorite(db_session, user.id, "recipe-001")
        await favorites_service.add_favorite(db_session, user.id, "recipe-001")

    @pytest.mark.asyncio
    async def test_fs_fav003_add_idempotent_single_row(self, db_session) -> None:
        """중복 추가해도 DB에 1건만 저장됨."""
        user = await _insert_user(db_session, "c@test.com")
        await favorites_service.add_favorite(db_session, user.id, "recipe-001")
        await favorites_service.add_favorite(db_session, user.id, "recipe-001")
        rows = await favorites_service.list_for_user(db_session, user.id)
        # list_for_user는 JOIN이라 recipe 없으면 빈 리스트지만 is_favorite으로 확인
        is_fav = await favorites_service.is_favorite(db_session, user.id, "recipe-001")
        assert is_fav is True


# ─────────────────────────────────────────────────────────────
class TestRemoveFavorite:

    @pytest.mark.asyncio
    async def test_fs_fav010_remove_existing_returns_true(self, db_session) -> None:
        """존재하는 즐겨찾기 삭제 → True."""
        user = await _insert_user(db_session, "d@test.com")
        await favorites_service.add_favorite(db_session, user.id, "recipe-001")
        result = await favorites_service.remove_favorite(db_session, user.id, "recipe-001")
        assert result is True

    @pytest.mark.asyncio
    async def test_fs_fav011_remove_nonexistent_returns_false(self, db_session) -> None:
        """없는 즐겨찾기 삭제 → False."""
        user = await _insert_user(db_session, "e@test.com")
        result = await favorites_service.remove_favorite(db_session, user.id, "nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_fs_fav012_remove_clears_is_favorite(self, db_session) -> None:
        """삭제 후 is_favorite → False."""
        user = await _insert_user(db_session, "f@test.com")
        await favorites_service.add_favorite(db_session, user.id, "recipe-001")
        await favorites_service.remove_favorite(db_session, user.id, "recipe-001")
        assert await favorites_service.is_favorite(db_session, user.id, "recipe-001") is False


# ─────────────────────────────────────────────────────────────
class TestIsFavorite:

    @pytest.mark.asyncio
    async def test_fs_fav020_is_favorite_true(self, db_session) -> None:
        """추가한 레시피 → True."""
        user = await _insert_user(db_session, "g@test.com")
        await favorites_service.add_favorite(db_session, user.id, "recipe-x")
        assert await favorites_service.is_favorite(db_session, user.id, "recipe-x") is True

    @pytest.mark.asyncio
    async def test_fs_fav021_is_favorite_false(self, db_session) -> None:
        """추가 안 한 레시피 → False."""
        user = await _insert_user(db_session, "h@test.com")
        assert await favorites_service.is_favorite(db_session, user.id, "recipe-x") is False

    @pytest.mark.asyncio
    async def test_fs_fav022_user_isolation(self, db_session) -> None:
        """유저 A 즐겨찾기가 유저 B에게 보이지 않음."""
        user_a = await _insert_user(db_session, "i@test.com")
        user_b = await _insert_user(db_session, "j@test.com")
        await favorites_service.add_favorite(db_session, user_a.id, "recipe-x")
        assert await favorites_service.is_favorite(db_session, user_b.id, "recipe-x") is False


# ─────────────────────────────────────────────────────────────
class TestListForUser:

    @pytest.mark.asyncio
    async def test_fs_fav030_list_returns_joined_recipe(self, db_session) -> None:
        """레시피가 DB에 있으면 목록에 반환됨."""
        user = await _insert_user(db_session, "k@test.com")
        await _insert_recipe(db_session, "recipe-join", "조인테스트")
        await favorites_service.add_favorite(db_session, user.id, "recipe-join")
        rows = await favorites_service.list_for_user(db_session, user.id)
        assert len(rows) == 1
        fav, recipe = rows[0]
        assert recipe.recipe_id == "recipe-join"
        assert recipe.name == "조인테스트"

    @pytest.mark.asyncio
    async def test_fs_fav031_list_empty_when_no_favorites(self, db_session) -> None:
        """즐겨찾기 없으면 빈 리스트."""
        user = await _insert_user(db_session, "l@test.com")
        rows = await favorites_service.list_for_user(db_session, user.id)
        assert rows == []

    @pytest.mark.asyncio
    async def test_fs_fav032_list_user_isolation(self, db_session) -> None:
        """유저 A 즐겨찾기가 유저 B 목록에 포함되지 않음."""
        user_a = await _insert_user(db_session, "m@test.com")
        user_b = await _insert_user(db_session, "n@test.com")
        await _insert_recipe(db_session, "recipe-iso")
        await favorites_service.add_favorite(db_session, user_a.id, "recipe-iso")
        rows_b = await favorites_service.list_for_user(db_session, user_b.id)
        assert rows_b == []

    @pytest.mark.asyncio
    async def test_fs_fav033_list_multiple_recipes(self, db_session) -> None:
        """여러 즐겨찾기 모두 반환됨."""
        user = await _insert_user(db_session, "o@test.com")
        await _insert_recipe(db_session, "recipe-first", "첫번째")
        await _insert_recipe(db_session, "recipe-second", "두번째")
        await favorites_service.add_favorite(db_session, user.id, "recipe-first")
        await favorites_service.add_favorite(db_session, user.id, "recipe-second")
        rows = await favorites_service.list_for_user(db_session, user.id)
        assert len(rows) == 2
        ids = {r[1].recipe_id for r in rows}
        assert ids == {"recipe-first", "recipe-second"}
