"""간접·감정 자연어 실험 — 음식 단어가 없는 표현을 임베딩이 매핑하는가?

예: "아 오늘 짜증나"(매운거?), "기분 꿀꿀해"(위로음식?), "축하할 일"(특별한거?)
이런 입력은 음식 단어가 없어 TF-IDF는 거의 무력. 의미 임베딩이 감정→음식을 잡는지,
아니면 LLM 의도 파싱이 필요한지 실제 추천 결과로 판단한다.

실행: cd backend && python scripts/experiment_emotional_nl.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_BD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BD))
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-padding-1234567890")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("GEMINI_API_KEY", "")

from app.models.recipe_repository import RecipeRepository, get_repository, set_repository  # noqa: E402
from app.services import embedding_service as emb  # noqa: E402
from app.services import gemini_client as gem  # noqa: E402
from app.services import model_a as ma  # noqa: E402
from app.services import semantic_embedding_service as sem  # noqa: E402
from app.services.model_a import recommend_cold_storage  # noqa: E402
from scripts.evaluate_semantic_nl import load_corpus  # noqa: E402

# 음식 단어가 (거의) 없는 간접·감정 표현 — 진짜 어려운 케이스
EMO = [
    "아 오늘 진짜 짜증나",
    "기분이 꿀꿀하고 우울해",
    "스트레스 받아서 뭔가 확 땡겨",
    "축하할 일이 있어서 특별하게 먹고 싶어",
    "몸이 으슬으슬 추워",
    "입맛이 하나도 없어",
    "피곤한데 기운 나는 거",
    "혼자 조용히 위로받고 싶은 날",
]
PREFS = {"country": "한식", "food_type": "메인요리", "spicy": 3, "difficulty": "초보", "max_cook_min": 60}
FRIDGE = ["김치", "돼지고기", "두부", "대파", "마늘", "양파", "계란", "밥", "고추장", "떡", "어묵", "감자", "당근"]


async def _none(c, u):
    return None


async def main() -> int:
    set_repository(RecipeRepository(load_corpus()))
    repo = get_repository()
    emb._reset_for_tests()
    emb.fit_corpus(repo.list_all())
    if not sem.ensure_ready():
        print("❌ 의미 임베딩 미준비")
        return 1
    gem.gemini_reasons_for_model_a = _none
    import app.core.config as cfg
    object.__setattr__(cfg.settings, "nl_weight", 0.35)
    ma.set_nl_retrieval_k(20)

    print("=" * 88)
    print("간접·감정 자연어 → 의미 임베딩 추천 결과 (음식 단어 없는 입력)")
    print(f"공통 조건: 한식·메인·맵기3 / 냉장고: {', '.join(FRIDGE[:6])}…")
    print("=" * 88)
    for ctx in EMO:
        emb.set_backend("semantic")
        a = await recommend_cold_storage(
            fridge_ingredients=FRIDGE, preferences=PREFS, user_allergies=[],
            repo=repo, user_context=ctx,
        )
        names = [r["name"] for r in a[:5]]
        print(f"\n「{ctx}」")
        print(f"   → {' · '.join(names) if names else '(빈 결과)'}")
    emb.set_backend(None)
    ma.set_nl_retrieval_k(None)
    print("\n" + "=" * 88)
    print("판단 기준: 결과가 입력 감정/의도에 '말이 되게' 연결되면 임베딩이 커버, ")
    print("뜬금없으면 LLM(제미나이) 의도 파싱 단계가 추가로 필요하다는 신호.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
