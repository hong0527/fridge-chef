"""냉장고 재료 서비스 (SRS FR-002, SDD §3.2 정규화)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.synonym_map import normalize
from app.models.orm import FridgeIngredient
from app.schemas.fridge import IngredientCreate


async def list_for_user(db: AsyncSession, user_id: int) -> list[FridgeIngredient]:
    rows = await db.scalars(
        select(FridgeIngredient).where(FridgeIngredient.user_id == user_id)
    )
    return list(rows)


async def add_for_user(
    db: AsyncSession, user_id: int, payload: IngredientCreate
) -> FridgeIngredient:
    item = FridgeIngredient(
        user_id=user_id,
        raw_name=payload.raw_name,
        normalized_name=normalize(payload.raw_name),
        quantity=payload.quantity,
        expires_at=payload.expires_at,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_for_user(db: AsyncSession, user_id: int, ingredient_id: int) -> bool:
    result = await db.execute(
        delete(FridgeIngredient).where(
            FridgeIngredient.id == ingredient_id,
            FridgeIngredient.user_id == user_id,
        )
    )
    await db.commit()
    return (result.rowcount or 0) > 0
