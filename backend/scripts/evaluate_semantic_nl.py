"""자연어 추천 ablation 평가 — TF-IDF(단어매칭) vs e5(의미 임베딩).

교수 질문("자연어 입력 → 추천이 잘 선택되는지 어떻게 측정?")에 답하는 정량 실험.
동일 평가셋(tests/fixtures/nl_relabel_set.json)에 대해 두 백엔드로 model_a Top-K 를 산출,
Recall@5 / nDCG@5 / MRR 을 비교하고 scipy paired t-test + Cohen's d 로 유의성을 본다.

핵심 가설: 패러프레이즈(category="paraphrase", MOOD_MAP 키 없는 다른 말투) 쿼리에서
의미 임베딩이 TF-IDF 보다 유의하게 높은 nDCG@5 를 얻는다.

실행:
    cd backend && python scripts/evaluate_semantic_nl.py
사전조건:
    1. /tmp/recipes_1667.pkl (운영 1667 코퍼스 캐시)
    2. python scripts/precompute_embeddings.py  (data/recipe_embeddings.npz 생성)
    3. sentence-transformers 설치
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-padding-1234567890")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("GEMINI_API_KEY", "")

from app.models.recipe_repository import RecipeRepository, get_repository, set_repository  # noqa: E402
from app.services import embedding_service as emb_mod  # noqa: E402
from app.services import gemini_client as gem_mod  # noqa: E402
from app.services import semantic_embedding_service as sem_mod  # noqa: E402
from app.services.model_a import recommend_cold_storage  # noqa: E402

RELABEL_PATH = _BACKEND_DIR / "tests" / "fixtures" / "nl_relabel_set.json"
CORPUS_CACHE = Path("/tmp/recipes_1667.pkl")
K = 5


# ──────────────────────────── 메트릭 ────────────────────────────
def recall_at_k(rec: list[str], rel: set[str], k: int) -> float:
    if not rel:
        return float("nan")
    return len(set(rec[:k]) & rel) / len(rel)


def ndcg_at_k(rec: list[str], rel: set[str], k: int) -> float:
    if not rel:
        return float("nan")
    dcg = sum(1.0 / math.log2(i + 2) for i, r in enumerate(rec[:k]) if r in rel)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel), k)))
    return dcg / idcg if idcg > 0 else 0.0


def mrr(rec: list[str], rel: set[str]) -> float:
    if not rel:
        return float("nan")
    for i, r in enumerate(rec):
        if r in rel:
            return 1.0 / (i + 1)
    return 0.0


# ──────────────────────────── 코퍼스 ────────────────────────────
def load_corpus() -> list:
    from app.models.recipe import Recipe
    import pickle
    if not CORPUS_CACHE.exists():
        print(f"❌ {CORPUS_CACHE} 없음 — 1667 코퍼스 캐시 필요")
        sys.exit(1)
    with CORPUS_CACHE.open("rb") as f:
        rows = pickle.load(f)
    out = []
    for r in rows:
        try:
            ings = json.loads(r["whole_ingredients"]) if isinstance(r["whole_ingredients"], str) else r["whole_ingredients"]
        except Exception:
            ings = []
        try:
            allg = json.loads(r["allergens"]) if isinstance(r["allergens"], str) else (r["allergens"] or [])
        except Exception:
            allg = []
        out.append(Recipe(
            recipe_id=str(r["recipe_id"]), name=r["name"], whole_ingredients=list(ings),
            cook_min=int(r.get("cook_min", 30)), spicy=int(r.get("spicy", 1)),
            difficulty_level=int(r.get("difficulty_level", 1)), is_low_calorie=bool(r.get("is_low_calorie", False)),
            country=str(r.get("country", "kr")), theme=str(r.get("theme", "main")), allergens=list(allg),
        ))
    return out


def expand_expected(names: list[str], repo) -> set[str]:
    """expected 이름 부분문자열 → 코퍼스 내 매칭 recipe_id 집합."""
    out: set[str] = set()
    for rec in repo.list_all():
        for nm in names:
            if nm in rec.name:
                out.add(rec.recipe_id)
                break
    return out


# ──────────────────────────── 통계 ────────────────────────────
def paired_stats(a: list[float], b: list[float]) -> dict:
    """b - a 의 paired t-test + Cohen's d (paired). scipy 사용."""
    pairs = [(x, y) for x, y in zip(a, b) if not (math.isnan(x) or math.isnan(y))]
    n = len(pairs)
    if n < 2:
        return {"n": n, "mean_diff": float("nan"), "t": float("nan"), "p": float("nan"), "d": float("nan")}
    diffs = [y - x for x, y in pairs]
    mean_d = sum(diffs) / n
    sd = (sum((d - mean_d) ** 2 for d in diffs) / (n - 1)) ** 0.5
    try:
        from scipy import stats
        t, p = stats.ttest_rel([y for _, y in pairs], [x for x, _ in pairs])
        t, p = float(t), float(p)
    except Exception:
        t = mean_d / (sd / math.sqrt(n)) if sd > 0 else float("inf")
        p = float("nan")
    d = mean_d / sd if sd > 0 else float("inf")  # Cohen's d (paired)
    return {"n": n, "mean_diff": mean_d, "t": t, "p": p, "d": d}


async def run() -> int:
    if not RELABEL_PATH.exists():
        print(f"❌ {RELABEL_PATH} 없음")
        return 1
    data = json.loads(RELABEL_PATH.read_text(encoding="utf-8"))
    queries = data["queries"]

    repo = RecipeRepository(load_corpus())
    set_repository(repo)
    print(f"코퍼스 {len(repo.list_all())}건 로드")

    # TF-IDF fit + 의미 임베딩 준비 (둘 다 메모리에 올려두고 set_backend 로 토글)
    emb_mod._reset_for_tests()
    emb_mod.fit_corpus(repo.list_all())
    sem_ok = sem_mod.ensure_ready()
    if not sem_ok:
        print("❌ 의미 임베딩 준비 실패 — precompute_embeddings.py 실행 + sentence-transformers 설치 확인")
        return 1
    print(f"의미 임베딩 준비: {sem_mod.stats()}")

    # 자연어 의미검색 후보 주입 + 가중치 (해결책 적용). EVAL_RETRIEVAL_K=0 으로 끄면 '재정렬 전용' 비교.
    from app.services import model_a as ma_mod
    import app.core.config as cfg
    retrieval_k = int(os.getenv("EVAL_RETRIEVAL_K", "20"))
    nl_weight = float(os.getenv("EVAL_NL_WEIGHT", "0.35"))
    ma_mod.set_nl_retrieval_k(retrieval_k)
    object.__setattr__(cfg.settings, "nl_weight", nl_weight)  # frozen dataclass 우회 (평가 전용)
    print(f"설정: NL retrieval_k={retrieval_k}, nl_weight={nl_weight}")

    # Gemini reason 호출 차단 (네트워크/비결정성 제거) — 순위엔 영향 없음
    async def _no_reason(candidates, user_context):
        return None
    gem_mod.gemini_reasons_for_model_a = _no_reason

    # expected 사전 확장
    for q in queries:
        q["_rel"] = expand_expected(q["expected_relevant"], repo)

    backends = ["tfidf", "semantic", "hybrid"]
    results: dict[str, list[dict]] = {b: [] for b in backends}
    for backend in backends:
        emb_mod.set_backend(backend)
        for q in queries:
            a = await recommend_cold_storage(
                fridge_ingredients=q["fridge_ingredients"],
                preferences=q["preferences"],
                user_allergies=[],
                repo=repo,
                user_context=q["user_context"],
            )
            ids = [r["recipe_id"] for r in a]
            rel = q["_rel"]
            results[backend].append({
                "id": q["id"], "category": q["category"], "ctx": q["user_context"],
                "n_cand": len(ids), "n_rel": len(rel),
                "rel_in_returned": len(set(ids) & rel),  # 정답이 후보(Top-10)에 도달했나 (재정렬 천장)
                "recall": recall_at_k(ids, rel, K), "ndcg": ndcg_at_k(ids, rel, K), "mrr": mrr(ids, rel),
            })
    emb_mod.set_backend(None)
    ma_mod.set_nl_retrieval_k(None)

    _report(queries, results, backends)
    return 0


def _mean(xs: list[float]) -> float:
    v = [x for x in xs if not math.isnan(x)]
    return sum(v) / len(v) if v else float("nan")


def _report(queries, results, backends) -> None:
    print("\n" + "=" * 92)
    print(f"자연어 추천 ablation: TF-IDF(단어) vs e5(의미)   —   Top-{K}, {len(queries)} 쿼리")
    print("=" * 92)

    # 진단: 양쪽 0점의 원인 분해 (자연어 성능 이전의 구조 문제)
    no_label = [q["id"] for q in queries if len(q["_rel"]) == 0]
    # 모든 백엔드에서 정답이 후보에 한 번도 못 들어온 쿼리 (구조적 미도달)
    not_retrieved = [
        q["id"] for i, q in enumerate(queries)
        if len(q["_rel"]) > 0 and all(results[b][i]["rel_in_returned"] == 0 for b in backends)
    ]
    print("\n[진단 — 자연어 점수 이전의 구조 병목]")
    print(f"  정답 라벨 0건(코퍼스에 이름 부재 등): {len(no_label)}/{len(queries)}  {no_label}")
    print(f"  모든 백엔드에서 후보(Top-10) 미도달: {len(not_retrieved)}/{len(queries)}  {not_retrieved}")
    print("  → 위 쿼리는 어떤 방법이든 0점. NL retrieval_k 확대 또는 맵기/난이도 필터 완화 영역.")

    hdr = "".join(f"{b:>11s}" for b in backends)
    # 전체 평균
    print("\n[전체 평균]")
    print(f"  {'Metric':<10s}{hdr}")
    for label, key in [("Recall@5", "recall"), ("nDCG@5", "ndcg"), ("MRR", "mrr")]:
        vals = "".join(f"{_mean([r[key] for r in results[b]]):>11.3f}" for b in backends)
        print(f"  {label:<10s}{vals}")

    # 카테고리별 nDCG@5
    print("\n[카테고리별 nDCG@5]")
    cats = sorted({q["category"] for q in queries})
    print(f"  {'category':<12s}{'n':>4s}{hdr}")
    for cat in cats:
        idx = [i for i, q in enumerate(queries) if q["category"] == cat]
        vals = "".join(f"{_mean([results[b][i]['ndcg'] for i in idx]):>11.3f}" for b in backends)
        star = "  ★핵심" if cat == "paraphrase" else ""
        print(f"  {cat:<12s}{len(idx):>4d}{vals}{star}")

    # paired t-test — 각 백엔드 vs TF-IDF 베이스라인
    print("\n[paired t-test (백엔드 - TF-IDF), scipy.ttest_rel]")
    for scope, idx in [("전체", list(range(len(queries)))),
                       ("paraphrase", [i for i, q in enumerate(queries) if q["category"] == "paraphrase"])]:
        for b in backends:
            if b == "tfidf":
                continue
            for label, key in [("nDCG@5", "ndcg"), ("Recall@5", "recall")]:
                base = [results["tfidf"][i][key] for i in idx]
                cand = [results[b][i][key] for i in idx]
                s = paired_stats(base, cand)
                sig = "유의(p<0.05)" if (not math.isnan(s["p"]) and s["p"] < 0.05) else \
                      ("비유의" if not math.isnan(s["p"]) else "p계산불가")
                print(f"  [{scope:<10s}] {b:<9s} {label:<9s} n={s['n']:>2d}  meanΔ={s['mean_diff']:+.3f}  "
                      f"t={s['t']:+.2f}  p={s['p']:.4f}  d={s['d']:+.2f}  → {sig}")

    # 패러프레이즈 쿼리별 상세
    print("\n[패러프레이즈 쿼리별 nDCG@5 (말투 바꿔도 의미 매칭되는가)]")
    print(f"  {'ID':5s}" + "".join(f"{b:>9s}" for b in backends) + "  context")
    for i, q in enumerate(queries):
        if q["category"] != "paraphrase":
            continue
        vals = "".join(f"{results[b][i]['ndcg']:>9.3f}" for b in backends)
        print(f"  {q['id']:5s}{vals}  {q['user_context'][:38]}")

    print("\n주의(정직): expected_relevant 는 1차 시드다. 최종 보고서엔 독립 블라인드 재라벨링 +")
    print("Cohen's κ 일치도를 함께 보고할 것 (docs/NL_RELABELING_PROTOCOL.md). 표본 n 도 명시.")


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
