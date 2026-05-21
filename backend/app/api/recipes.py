"""/api/recipes/* — 레시피 단건 조회.

# NFR-EVAL-002 — recipe_id 화이트리스트 검증
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.orm import RecipeRow

router = APIRouter()


@router.get("/{recipe_id}")
async def get_recipe(recipe_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    row = await db.scalar(select(RecipeRow).where(RecipeRow.recipe_id == recipe_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="레시피를 찾을 수 없습니다."
        )
    return {
        "recipe_id": row.recipe_id,
        "name": row.name,
        "whole_ingredients": row.whole_ingredients,
        "steps": row.steps,
        "cook_min": row.cook_min,
        "spicy": row.spicy,
        "difficulty_level": row.difficulty_level,
        "is_low_calorie": row.is_low_calorie,
        "country": row.country,
        "theme": row.theme,
        "allergens": row.allergens,
        "image_url": row.image_url,
    }
