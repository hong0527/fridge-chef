"""자연어 설계 실험 — 2가지 결정적 질문에 수치로 답한다.

실험 1: Model A('냉털'=지금 만들 수 있는) 에 NL 의미검색 후보를 주입하면, 재료가 부족한
        레시피(missing>0)가 얼마나 섞이는가? → A/B 역할 분리 위반 정도 측정.
실험 2: MOOD_MAP(expand_context) 수동 사전이 의미 임베딩 도입 후에도 효과가 있는가?
        백엔드별 expand_context on/off nDCG@5 비교.

실행: cd backend && python scripts/experiment_nl_design.py
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
from pathlib import Path

_BD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BD))
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-padding-1234567890")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("GEMINI_API_KEY", "")

from app.core.synonym_map import normalize_list  # noqa: E402
from app.models.recipe_repository import RecipeRepository, get_repository, set_repository  # noqa: E402
from app.services import embedding_service as emb  # noqa: E402
from app.services import gemini_client as gem  # noqa: E402
from app.services import model_a as ma  # noqa: E402
from app.services import semantic_embedding_service as sem  # noqa: E402
from app.services.model_a import BASIC_SEASONINGS, recommend_cold_storage  # noqa: E402
from scripts.evaluate_semantic_nl import load_corpus, ndcg_at_k, expand_expected, _mean  # noqa: E402

RELABEL = _BD / "tests" / "fixtures" / "nl_relabel_set.json"
K = 5


async def _none(c, u):
    return None


def _missing_count(fridge: set[str], recipe) -> int:
    main = [i for i in recipe.whole_ingredients if i not in BASIC_SEASONINGS]
    return sum(1 for i in main if i not in fridge)


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

    queries = json.loads(RELABEL.read_text(encoding="utf-8"))["queries"]
    for q in queries:
        q["_rel"] = expand_expected(q["expected_relevant"], repo)

    # ── 실험 1: Model A 주입 시 재료 부족(missing) 분포 ──
    print("=" * 84)
    print("실험 1 — Model A(냉털)에 NL 후보 주입 시 '재료 부족' 정도 (A/B 역할 분리 위반 측정)")
    print("=" * 84)
    print("Model A 는 '지금 가진 재료로 만들 수 있는' 추천이어야 한다. missing=0 이 이상적,")
    print("재료겹침 hard filter(overlap≥0.6)는 missing 을 주재료의 ~40% 까지 허용한다.")
    print("NL 주입은 overlap 필터를 우회하므로 missing 이 더 커질 수 있다 — 그 정도를 측정.\n")

    for backend in ["tfidf", "hybrid"]:
        emb.set_backend(backend)
        for inj_k, tag in [(0, "주입 OFF"), (20, "주입 ON k=20")]:
            ma.set_nl_retrieval_k(inj_k)
            all_missing: list[int] = []
            zero = 0
            over5 = 0
            total = 0
            for q in queries:
                fridge = set(normalize_list(q["fridge_ingredients"]))
                a = await recommend_cold_storage(
                    fridge_ingredients=q["fridge_ingredients"], preferences=q["preferences"],
                    user_allergies=[], repo=repo, user_context=q["user_context"],
                )
                for r in a:
                    rec = repo.get(r["recipe_id"])
                    m = _missing_count(fridge, rec)
                    all_missing.append(m)
                    total += 1
                    if m == 0:
                        zero += 1
                    if m > 5:
                        over5 += 1
            avg = statistics.mean(all_missing) if all_missing else 0
            print(f"  [{backend:7s} {tag:12s}] 추천 {total}건 | 평균 missing={avg:.2f} | "
                  f"missing=0(완전냉털) {zero/total*100:4.1f}% | missing>5(B영역) {over5/total*100:4.1f}%")
        emb.set_backend(None)
        ma.set_nl_retrieval_k(None)

    # ── 실험 2: MOOD_MAP(expand_context) on/off ──
    print("\n" + "=" * 84)
    print("실험 2 — MOOD_MAP 수동 사전(expand_context)이 의미 임베딩 후에도 필요한가? (nDCG@5)")
    print("=" * 84)
    print("expand_context OFF = user_context 원문만 사용 (사전 키워드 추가 안 함).\n")

    orig_expand = ma.expand_context
    for backend in ["tfidf", "semantic", "hybrid"]:
        emb.set_backend(backend)
        ma.set_nl_retrieval_k(20)
        row = {}
        for mode, fn in [("MOOD_MAP ON", orig_expand), ("MOOD_MAP OFF", lambda x: x)]:
            ma.expand_context = fn
            ndcgs = []
            for q in queries:
                a = await recommend_cold_storage(
                    fridge_ingredients=q["fridge_ingredients"], preferences=q["preferences"],
                    user_allergies=[], repo=repo, user_context=q["user_context"],
                )
                ids = [r["recipe_id"] for r in a]
                ndcgs.append(ndcg_at_k(ids, q["_rel"], K))
            row[mode] = _mean(ndcgs)
        ma.expand_context = orig_expand
        delta = row["MOOD_MAP ON"] - row["MOOD_MAP OFF"]
        if delta > 0.01:
            verdict = "사전 효과 있음"
        elif delta < -0.01:
            verdict = "사전이 오히려 해"
        else:
            verdict = "차이 미미 — 사전 불필요"
        print(f"  [{backend:8s}] ON={row['MOOD_MAP ON']:.3f}  OFF={row['MOOD_MAP OFF']:.3f}  "
              f"Δ(ON-OFF)={delta:+.3f}  → {verdict}")
    emb.set_backend(None)
    ma.set_nl_retrieval_k(None)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
