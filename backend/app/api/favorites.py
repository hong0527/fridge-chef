"""/api/favorites/* — 즐겨찾기 CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import User, get_current_user
from app.core.db import get_db
from app.schemas.favorites import FavoriteItem, FavoriteListResponse, FavoriteStatus
from app.services import favorites_service

router = APIRouter()


@router.get("", response_model=FavoriteListResponse)
async def list_favorites(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> FavoriteListResponse:
    rows = await favorites_service.list_for_user(db, int(user.user_id))
    items = [
        FavoriteItem(
            recipe_id=recipe.recipe_id,
            name=recipe.name,
            cook_min=recipe.cook_min,
            spicy=recipe.spicy,
            difficulty_level=recipe.difficulty_level,
            country=recipe.country,
            theme=recipe.theme,
            image_url=recipe.image_url,
            favorited_at=fav.created_at,
        )
        for fav, recipe in rows
    ]
    return FavoriteListResponse(items=items, total=len(items))


@router.get("/{recipe_id}", response_model=FavoriteStatus)
async def check_favorite(
    recipe_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FavoriteStatus:
    is_fav = await favorites_service.is_favorite(db, int(user.user_id), recipe_id)
    return FavoriteStatus(is_favorite=is_fav)


@router.post("/{recipe_id}", status_code=status.HTTP_201_CREATED)
async def add_favorite(
    recipe_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await favorites_service.add_favorite(db, int(user.user_id), recipe_id)
    return {"message": "즐겨찾기에 추가했습니다."}


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def remove_favorite(
    recipe_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    ok = await favorites_service.remove_favorite(db, int(user.user_id), recipe_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="즐겨찾기를 찾을 수 없습니다.")
