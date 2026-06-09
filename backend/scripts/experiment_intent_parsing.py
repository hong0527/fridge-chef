"""Gemini 의도 파싱 효과 증명 — 감정/간접 입력의 before(원문임베딩)/after(의도파싱+임베딩).

실제 Gemini API 호출 (.env GEMINI_API_KEY 사용).
실행: cd backend && python scripts/experiment_intent_parsing.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_BD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BD))

# .env 의 GEMINI_API_KEY 를 환경변수로 로드 (config 가 os.getenv 로 읽음)
_ENV = _BD.parent / ".env"
if _ENV.exists():
    for line in _ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("GEMINI_API_KEY") and "=" in line:
            os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-padding-1234567890")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app.models.recipe_repository import (  # noqa: E402
    RecipeRepository,
    get_repository,
    set_repository,
)
from app.services import embedding_service as emb  # noqa: E402
from app.services import gemini_client as gem  # noqa: E402
from app.services import model_a as ma  # noqa: E402
from app.services import semantic_embedding_service as sem  # noqa: E402
from app.services.gemini_intent import parse_food_intent  # noqa: E402
from app.services.model_a import recommend_cold_storage  # noqa: E402
from scripts.evaluate_semantic_nl import load_corpus  # noqa: E402

EMO = [
    "아 오늘 진짜 짜증나",
    "축하할 일이 있어서 특별하게 먹고 싶어",
    "몸이 으슬으슬 추워",
    "입맛이 하나도 없어",
    "기분이 꿀꿀하고 우울해",
]
PREFS = {"country": "한식", "food_type": "메인요리", "spicy": 3, "difficulty": "초보", "max_cook_min": 60}
FRIDGE = ["김치", "돼지고기", "두부", "대파", "마늘", "양파", "계란", "밥", "고추장", "떡", "어묵", "감자", "당근", "소고기", "고춧가루"]


async def _none(c, u):
    return None


async def _rec(ctx, prefs):
    a = await recommend_cold_storage(
        fridge_ingredients=FRIDGE, preferences=prefs, user_allergies=[],
        repo=get_repository(), user_context=ctx,
    )
    return [r["name"] for r in a[:5]]


async def main() -> int:
    set_repository(RecipeRepository(load_corpus()))
    emb._reset_for_tests()
    emb.fit_corpus(get_repository().list_all())
    if not sem.ensure_ready():
        print("❌ 의미 임베딩 미준비")
        return 1
    gem.gemini_reasons_for_model_a = _none
    import app.core.config as cfg
    object.__setattr__(cfg.settings, "nl_weight", 0.35)
    ma.set_nl_retrieval_k(20)
    emb.set_backend("semantic")

    print(f"Gemini key 설정: {'OK' if cfg.settings.gemini_api_key else '없음(폴백됨)'}")
    print("=" * 90)
    for ctx in EMO:
        intent = await parse_food_intent(ctx)
        before = await _rec(ctx, PREFS)
        prefs2 = {**PREFS, "spicy": intent["spicy"] or PREFS["spicy"]}
        after = await _rec(intent["food_query"] or ctx, prefs2)
        print(f"\n입력: 「{ctx}」")
        print(f"  Gemini 의도파싱 → 「{intent['food_query']}」 (맵기추정={intent['spicy']}, src={intent['source']})")
        print(f"  이전(원문 임베딩)      : {' · '.join(before)}")
        print(f"  지금(의도파싱+임베딩)  : {' · '.join(after)}")
    emb.set_backend(None)
    ma.set_nl_retrieval_k(None)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
