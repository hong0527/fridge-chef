from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FavoriteItem(BaseModel):
    recipe_id: str
    name: str
    cook_min: int
    spicy: int
    difficulty_level: int
    country: str
    theme: str
    image_url: Optional[str]
    favorited_at: datetime


class FavoriteListResponse(BaseModel):
    items: list[FavoriteItem]
    total: int


class FavoriteStatus(BaseModel):
    is_favorite: bool
