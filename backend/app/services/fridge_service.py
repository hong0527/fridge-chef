"""냉장고 재료 서비스 (SRS FR-002, SDD §3.2 정규화)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.synonym_map import SYNONYM_MAP, normalize
from app.models.orm import FridgeIngredient
from app.schemas.fridge import IngredientCreate


# NFR-USE-001 — 자동완성으로 재료 입력 시간 단축 (3분 이내 추천 흐름)
def search_ingredient_suggestions(q: str, limit: int = 8) -> list[str]:
    """SYNONYM_MAP 기반 재료 이름 자동완성 (RF-01: Service Layer, RF-04: 동의어 자체 반환).

    동의어("달걀") 입력 시 동의어 자체를 반환.
    정규형("계란") 입력 시 정규형을 반환.
    """
    needle = q.strip().lower()
    if not needle:
        return []
    seen: set[str] = set()
    results: list[str] = []
    for synonym, canonical in SYNONYM_MAP.items():
        if needle in synonym.lower() and synonym not in seen:
            seen.add(synonym)
            results.append(synonym)
        if needle in canonical.lower() and canonical not in seen:
            seen.add(canonical)
            results.append(canonical)
        if len(results) >= limit:
            break
    return results


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
