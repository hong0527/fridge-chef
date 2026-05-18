"""냉장고 재료 스키마 (SRS FR-002)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IngredientCreate(BaseModel):
    raw_name: str = Field(min_length=1, max_length=128)
    quantity: str | None = Field(default=None, max_length=64)
    expires_at: datetime | None = None


class IngredientResponse(BaseModel):
    id: int
    raw_name: str
    normalized_name: str
    quantity: str | None
    expires_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class IngredientListResponse(BaseModel):
    items: list[IngredientResponse]
    total: int
