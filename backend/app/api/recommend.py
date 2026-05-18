"""POST /api/recommend — 듀얼 추천 엔드포인트.

SDD §4: RecommendService.recommend_dual() 위임.
SRS FR-005, FR-007, NFR-PERF-003, NFR-EVAL-001/002.

라우터는 main.py 에서 prefix="/api/recommend" 로 등록되므로 path는 "" 로 둔다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import User, get_current_user
from app.schemas.recommend import RecommendRequest, RecommendResponse
from app.services.recommend_service import recommend_dual

router = APIRouter()


@router.post("", response_model=RecommendResponse)
async def post_recommend(
    req: RecommendRequest,
    user: User = Depends(get_current_user),
) -> RecommendResponse:
    """듀얼 추천:
    - model_a: 냉털 추천 10개 (코사인 유사도)
    - model_b: 부족재료 추천 3개 (복합점수+Gemini)

    SRS FR-007: preferences.use_saved_allergies=True일 때 user.saved_allergies 적용.
    """
    prefs_dict = req.preferences.model_dump()
    user_allergies: list[str] = []
    if req.preferences.use_saved_allergies:
        user_allergies = list(user.saved_allergies)

    result = await recommend_dual(
        fridge_ingredients=req.fridge_ingredients,
        preferences=prefs_dict,
        user_allergies=user_allergies,
        user_context=req.preferences.user_context,
    )
    return RecommendResponse(**result)
