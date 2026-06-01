"""추천 API 요청/응답 스키마 (SDD §4 RecommendService 인터페이스)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Preferences(BaseModel):
    """사용자 선호 입력. SRS FR-003 참조."""

    spicy: int = Field(default=3, ge=1, le=5, description="맵기 1–5")
    difficulty: str = Field(default="초보", description="초보|중급|고급")
    diet: bool = Field(default=False, description="저칼로리 우선")
    # NFR-EVAL-001 안전 정책 — 저장 알레르기는 항상 적용. 토글로 우회 불가.
    # (기존 use_saved_allergies 필드는 코드와 모순되어 제거: 토글로 알레르기 노출 위험 차단)
    food_type: str = Field(default="메인요리", description="메인요리|반찬|국물|디저트|음료")
    country: str = Field(default="한식", description="한식|중식|일식|양식|기타")
    max_cook_min: int = Field(default=60, ge=1, le=600, description="최대 조리시간")
    # Prompt injection 방어 — 길이 제한. Gemini 클라이언트에서 escape 처리.
    user_context: str = Field(default="", max_length=200, description="자연어 문맥(예: '와인과 같이')")


class RecommendRequest(BaseModel):
    fridge_ingredients: list[str] = Field(default_factory=list, description="냉장고 보유 재료")
    preferences: Preferences = Field(default_factory=Preferences)


class RecipeBrief(BaseModel):
    recipe_id: str
    name: str
    cook_min: int
    spicy: int
    difficulty_level: int
    country: str
    theme: str
    image_url: str | None = None


class ModelACandidate(RecipeBrief):
    score: float = Field(..., description="코사인 유사도 [0,1]")


class ModelBCandidate(RecipeBrief):
    final_score: float
    have: list[str]
    missing: list[str]
    reason: str = Field(default="", description="Gemini 한국어 추천 이유 (실패 시 빈 문자열)")


class RecommendResponse(BaseModel):
    model_a: list[ModelACandidate]
    model_b: list[ModelBCandidate]
