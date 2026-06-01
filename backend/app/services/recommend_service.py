"""RecommendService — 모델 A·B 동시 실행 오케스트레이션.

SDD §4 시퀀스:
- asyncio.gather()로 모델 A·B 동시 실행
- 10초 타임아웃 (NFR-PERF-003)
- 결과: {model_a: [...10개...], model_b: [...3개 with Gemini 이유...]}
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.models.recipe_repository import RecipeRepository, get_repository
from app.services.model_a import recommend_cold_storage
from app.services.model_b import recommend_missing_ingredients

_logger = logging.getLogger(__name__)


async def _safe_run(name: str, coro, timeout_s: float) -> list[dict]:
    """단일 모델 독립 격리 — 한쪽 실패가 다른 쪽 결과 폐기를 막음 (NFR-PERF-003, NFR-REL-001)."""
    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except TimeoutError:
        _logger.warning("%s 타임아웃 (%.1fs)", name, timeout_s)
        return []
    except Exception:
        _logger.exception("%s 실패", name)
        return []


async def recommend_dual(
    fridge_ingredients: list[str],
    preferences: dict,
    user_allergies: list[str],
    user_context: str = "",
    repo: RecipeRepository | None = None,
) -> dict:
    """모델 A·B 병렬 호출 후 단일 응답 객체로 결합.

    NFR-PERF-003: 전체 10초 타임아웃. 초과 시 두 모델 모두 빈 리스트로 폴백.
    """
    repo = repo or get_repository()

    async def _run_a() -> list[dict]:
        return await recommend_cold_storage(
            fridge_ingredients=fridge_ingredients,
            preferences=preferences,
            user_allergies=user_allergies,
            repo=repo,
        )

    async def _run_b() -> list[dict]:
        return await recommend_missing_ingredients(
            fridge_ingredients=fridge_ingredients,
            preferences=preferences,
            user_allergies=user_allergies,
            user_context=user_context,
            repo=repo,
        )

    model_a, model_b = await asyncio.gather(
        _safe_run("model_a", _run_a(), settings.recommend_timeout_s),
        _safe_run("model_b", _run_b(), settings.recommend_timeout_s),
    )
    # CRITICAL #C6 — model_a/b 추천 결과 중복 차단 ('왜 같은 메뉴 두 번?' UX).
    # 다만 dedup이 너무 강하면 model_b가 빈 결과가 됨 (사용자 시연: 계란·쌀·한식 메인
    # 시 model_a=6개 / model_b=0개 발생). 보수적 완화:
    #   - Top-K dedup: model_a 상위 3개와만 비교 (가장 강한 추천만 우선 보호)
    #   - 부족 fallback: 그 결과 model_b가 비면 dedup 무시 (사용자에게 빈 결과보다 일부
    #     중복이 낫다는 UX 정책)
    if model_b:
        a_top_ids = {r["recipe_id"] for r in model_a[:3]}
        deduped = [r for r in model_b if r["recipe_id"] not in a_top_ids]
        model_b = deduped if deduped else model_b
    return {"model_a": model_a, "model_b": model_b}
