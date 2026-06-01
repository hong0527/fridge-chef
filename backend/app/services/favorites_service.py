from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Favorite, RecipeRow


async def is_favorite(db: AsyncSession, user_id: int, recipe_id: str) -> bool:
    row = await db.scalar(
        select(Favorite.id).where(Favorite.user_id == user_id, Favorite.recipe_id == recipe_id)
    )
    return row is not None


async def add_favorite(db: AsyncSession, user_id: int, recipe_id: str) -> None:
    if await is_favorite(db, user_id, recipe_id):
        return
    db.add(Favorite(user_id=user_id, recipe_id=recipe_id))
    await db.commit()


async def remove_favorite(db: AsyncSession, user_id: int, recipe_id: str) -> bool:
    result = await db.execute(
        delete(Favorite).where(Favorite.user_id == user_id, Favorite.recipe_id == recipe_id)
    )
    await db.commit()
    return result.rowcount > 0


async def list_for_user(db: AsyncSession, user_id: int) -> list[tuple[Favorite, RecipeRow]]:
    rows = await db.execute(
        select(Favorite, RecipeRow)
        .join(RecipeRow, Favorite.recipe_id == RecipeRow.recipe_id)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())
    )
    return list(rows.all())
