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

    # 자연어 의도파싱 — 자유 입력("오늘 짜증나")을 Gemini가 음식 묘사("맵고 얼큰한 볶음")로 번역해
    # 검색어를 풍부화한다. 그 결과를 기존 TF-IDF 매칭에 그대로 태우므로 e5 등 무거운 모델 불필요(운영 가능).
    # 빈 입력이면 호출 안 함. 실패/타임아웃/레이트리밋 시 원문으로 폴백(parse_food_intent 내부 + 여기 except).
    effective_context = user_context
    if settings.nl_intent_enabled and user_context.strip():
        try:
            from app.services.gemini_intent import parse_food_intent

            intent = await asyncio.wait_for(
                parse_food_intent(user_context), timeout=settings.gemini_timeout_s
            )
            # 실제 Gemini 번역이 성공한 경우만 풍부화 (폴백/키없음 시 원문 중복 방지).
            if intent.get("source") == "gemini" and intent.get("food_query"):
                # 원문 + 번역문 결합 — 원문 단어와 번역된 음식 단어 모두 TF-IDF 매칭에 활용.
                effective_context = f"{user_context} {intent['food_query']}".strip()
        except Exception:  # noqa: BLE001 — 네트워크/타임아웃/파싱 실패 시 원문 사용 (안전).
            effective_context = user_context

    async def _run_a() -> list[dict]:
        return await recommend_cold_storage(
            fridge_ingredients=fridge_ingredients,
            preferences=preferences,
            user_allergies=user_allergies,
            repo=repo,
            user_context=effective_context,
        )

    async def _run_b() -> list[dict]:
        return await recommend_missing_ingredients(
            fridge_ingredients=fridge_ingredients,
            preferences=preferences,
            user_allergies=user_allergies,
            user_context=effective_context,
            repo=repo,
        )

    model_a, model_b = await asyncio.gather(
        _safe_run("model_a", _run_a(), settings.recommend_timeout_s),
        _safe_run("model_b", _run_b(), settings.recommend_timeout_s),
    )
    # dedup 제거 — Model A(missing==0) 와 Model B(missing 1~5) 가 정의상 자연 분리되어
    # 같은 recipe_id 가 양쪽에 동시 등장 불가. SDD §3.2 정의 충실.
    return {"model_a": model_a, "model_b": model_b}
