"""자연어 입력 before/after 시연 — 같은 입력에 백엔드별 실제 추천 결과(레시피 이름) 출력.

실행: cd backend && python scripts/demo_nl_before_after.py
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

from app.models.recipe_repository import RecipeRepository, set_repository, get_repository  # noqa: E402
from app.services import embedding_service as emb  # noqa: E402
from app.services import gemini_client as gem  # noqa: E402
from app.services import model_a as ma  # noqa: E402
from app.services import semantic_embedding_service as sem  # noqa: E402
from app.services.model_a import recommend_cold_storage  # noqa: E402
from scripts.evaluate_semantic_nl import load_corpus  # noqa: E402

DEMOS = [
    ("장마철 추적추적 오는데 속 풀리게 뜨끈한 거",
     {"country": "한식", "food_type": "국물", "spicy": 3, "difficulty": "초보", "max_cook_min": 60},
     ["김치", "돼지고기", "두부", "대파", "마늘", "양파", "고춧가루", "된장"]),
    ("기념일에 근사하게 구운 고기 요리",
     {"country": "양식", "food_type": "메인요리", "spicy": 1, "difficulty": "고급", "max_cook_min": 40},
     ["소고기", "올리브유", "마늘", "버터", "양파", "감자", "후추"]),
    ("학창시절 떡볶이 같은 얼큰달콤한 거",
     {"country": "한식", "food_type": "메인요리", "spicy": 4, "difficulty": "초보", "max_cook_min": 30},
     ["떡", "어묵", "대파", "고추장", "양파", "계란", "고춧가루"]),
]


async def main() -> int:
    set_repository(RecipeRepository(load_corpus()))
    repo = get_repository()
    emb._reset_for_tests()
    emb.fit_corpus(repo.list_all())
    if not sem.ensure_ready():
        print("❌ 의미 임베딩 미준비 — precompute_embeddings.py 실행 필요")
        return 1
    ma.set_nl_retrieval_k(20)
    import app.core.config as cfg
    object.__setattr__(cfg.settings, "nl_weight", 0.35)

    async def _none(c, u):  # Gemini reason 차단
        return None
    gem.gemini_reasons_for_model_a = _none

    for ctx, prefs, fridge in DEMOS:
        print("\n" + "=" * 80)
        print(f"입력 자연어: 「{ctx}」")
        print(f"  (선호: {prefs['country']}·{prefs['food_type']}·맵기{prefs['spicy']} / 냉장고: {', '.join(fridge[:5])}…)")
        print("-" * 80)
        for backend, label in [("tfidf", "이전(단어매칭 TF-IDF)"), ("semantic", "지금(의미 e5)"), ("hybrid", "하이브리드")]:
            emb.set_backend(backend)
            out = await recommend_cold_storage(
                fridge_ingredients=fridge, preferences=prefs, user_allergies=[],
                repo=repo, user_context=ctx,
            )
            names = [f"{r['name']}({r['score']:.2f})" for r in out[:5]]
            print(f"  {label:<22s}: {' · '.join(names) if names else '(빈 결과)'}")
        emb.set_backend(None)
    ma.set_nl_retrieval_k(None)
    print("\n" + "=" * 80)
    print("해석: 어휘가 겹치지 않는 표현일수록 의미/하이브리드가 의도에 맞는 메뉴를 끌어온다.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
