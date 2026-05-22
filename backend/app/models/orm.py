"""SQLAlchemy ORM 매핑 (SDD §2 클래스 다이어그램 → 테이블).

엔티티:
- User              : 회원 (이메일·해시비번·알레르기·선호도)
- FridgeIngredient  : 냉장고 재료 (사용자별)
- RecipeRow         : 레시피 카탈로그 (whole_ingredients 정규화)
- Rating            : 사용자별 평점 (1–5)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class User(Base):
    """SDD §2 User 엔티티."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    allergies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verification_token: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    email_verification_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    fridge_items: Mapped[list[FridgeIngredient]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    ratings: Mapped[list[Rating]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class FridgeIngredient(Base):
    """SDD §2 FridgeIngredient 엔티티 (사용자 냉장고 재료)."""

    __tablename__ = "fridge_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_name: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    quantity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="fridge_items")


class RecipeRow(Base):
    """SDD §2 Recipe 엔티티 (카탈로그 테이블)."""

    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    whole_ingredients: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    steps: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    cook_min: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    spicy: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    difficulty_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_low_calorie: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    country: Mapped[str] = mapped_column(String(8), default="kr", nullable=False)
    theme: Mapped[str] = mapped_column(String(16), default="main", nullable=False)
    allergens: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Rating(Base):
    """사용자별 레시피 평점 (1–5). SDD §2 Rating."""

    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipe_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="ratings")
