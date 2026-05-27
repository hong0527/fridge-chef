"""레시피 도메인 모델 (SDD §3.1 Recipe 엔티티)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Recipe:
    """단일 레시피 표현.

    Attributes:
        recipe_id: 화이트리스트 검증용 ID (NFR-EVAL-002).
        name: 표시명.
        whole_ingredients: 정규화된 재료 키워드 리스트.
        cook_min: 조리시간(분).
        spicy: 맵기 1–5.
        difficulty_level: 1=초보, 2=중급, 3=고급.
        is_low_calorie: 저칼로리 여부.
        country: 'kr' | 'cn' | 'jp' | 'west' | 'etc'.
        theme: 'main' | 'side' | 'soup' | 'dessert' | 'drink'.
        allergens: 알레르기 유발 정규화 키워드.
    """

    recipe_id: str
    name: str
    whole_ingredients: list[str]
    cook_min: int = 30
    spicy: int = 1
    difficulty_level: int = 1
    is_low_calorie: bool = False
    country: str = "kr"
    theme: str = "main"
    allergens: list[str] = field(default_factory=list)
    image_url: str | None = None  # /static/recipes/{cookid}.jpg

    def to_brief_dict(self) -> dict:
        return {
            "recipe_id": self.recipe_id,
            "name": self.name,
            "cook_min": self.cook_min,
            "spicy": self.spicy,
            "difficulty_level": self.difficulty_level,
            "country": self.country,
            "theme": self.theme,
            "image_url": self.image_url,
        }
