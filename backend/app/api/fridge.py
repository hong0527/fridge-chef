"""/api/fridge/* — 냉장고 재료 CRUD.

# SDD §3.2 — 입력 즉시 동의어 정규화
# JWT 인증: 모든 엔드포인트에 get_current_user Depends 적용
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User, get_current_user
from app.core.db import get_db
from app.schemas.fridge import (
    IngredientCreate,
    IngredientListResponse,
    IngredientResponse,
)
from app.services import fridge_service

router = APIRouter()


@router.get("", response_model=IngredientListResponse)
async def list_ingredients(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> IngredientListResponse:
    rows = await fridge_service.list_for_user(db, int(user.user_id))
    items = [IngredientResponse.model_validate(r) for r in rows]
    return IngredientListResponse(items=items, total=len(items))


@router.post("", response_model=IngredientResponse, status_code=status.HTTP_201_CREATED)
async def create_ingredient(
    payload: IngredientCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngredientResponse:
    item = await fridge_service.add_for_user(db, int(user.user_id), payload)
    return IngredientResponse.model_validate(item)


@router.delete("/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_ingredient(
    ingredient_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    ok = await fridge_service.delete_for_user(db, int(user.user_id), ingredient_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="재료를 찾을 수 없습니다.")


@router.get("/search")  # NFR-USE-001 — 자동완성으로 재료 입력 시간 단축
async def search_ingredients(
    q: str = "",
    _: User = Depends(get_current_user),  # RF-02: 기존 fridge 엔드포인트와 동일하게 인증 적용
) -> dict:
    """재료 이름 자동완성 — SYNONYM_MAP 기반 (RF-01: Service Layer, RF-02: 인증)."""
    results = fridge_service.search_ingredient_suggestions(q)
    return {"suggestions": results}
