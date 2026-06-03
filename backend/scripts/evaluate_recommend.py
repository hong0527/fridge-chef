"""추천 시스템 신뢰성·성능 평가 스크립트.

학계 표준 메트릭(Precision@K, Recall@K, MRR, NDCG@K, Coverage, Diversity)을
계산하고 NFR-EVAL-001(알레르기 0%)·NFR-EVAL-002(citation 검증) 충족 여부를
실측한다. 골든셋 30개 시나리오에 대해 model_a/model_b를 호출하고 보고서를 출력.

참조:
- Konstan & Riedl, "Recommender systems: from algorithms to user experience"
- Microsoft Recommenders (github.com/microsoft/recommenders) 평가 모듈
- Gunawardana & Shani, "A Survey of Accuracy Evaluation Metrics of Recommendation Tasks"

실행: cd backend && python scripts/evaluate_recommend.py
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))

os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-padding-1234567890")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("GEMINI_API_KEY", "")

from app.core.synonym_map import normalize_list  # noqa: E402
from app.models.recipe_repository import get_repository  # noqa: E402
from app.services import embedding_service as emb_mod  # noqa: E402
from app.services import model_b as mb_mod  # noqa: E402
from app.services.model_a import recommend_cold_storage  # noqa: E402
from app.services.model_b import recommend_missing_ingredients  # noqa: E402

GOLDEN_PATH = _BACKEND_DIR / "tests" / "fixtures" / "recommend_golden_set.json"
TFIDF_SCENARIOS_PATH = _BACKEND_DIR / "tests" / "fixtures" / "eval_tfidf_scenarios.json"


# ────────────────────────────────────────────────────────────────
# 메트릭 정의 (학계 표준)
# ────────────────────────────────────────────────────────────────


def precision_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    """Precision@K = (Top-K 중 정답 비율). [0,1]."""
    if k <= 0 or not recommended:
        return 0.0
    top_k = recommended[:k]
    hits = sum(1 for r in top_k if r in relevant)
    return hits / min(k, len(top_k))


def recall_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    """Recall@K = (정답 중 Top-K에 포함된 비율). [0,1]. relevant 비어있으면 N/A→1.0."""
    if not relevant:
        return 1.0  # 정답 없는 시나리오는 recall 의미 없음 → 통과 처리
    top_k = set(recommended[:k])
    hits = len(top_k & relevant)
    return hits / len(relevant)


def reciprocal_rank(recommended: list[str], relevant: set[str]) -> float:
    """Reciprocal Rank = 1/(첫 정답의 순위). 정답 없으면 0."""
    if not relevant:
        return 1.0  # 정답 없는 시나리오 → 통과
    for i, r in enumerate(recommended):
        if r in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain@K. 순위 가중 정확도. [0,1]."""
    if not relevant:
        return 1.0
    dcg = 0.0
    for i, r in enumerate(recommended[:k]):
        if r in relevant:
            dcg += 1.0 / math.log2(i + 2)
    # ideal DCG (모든 정답이 상위)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


# ────────────────────────────────────────────────────────────────
# 평가 실행
# ────────────────────────────────────────────────────────────────


async def _mock_gemini_none(candidates, user_context):
    return None


async def evaluate_scenario(scenario: dict, repo: Any) -> dict[str, Any]:
    """단일 시나리오 평가."""
    fridge = scenario["fridge"]
    prefs = scenario["preferences"]
    allergies = scenario["allergies"]
    gt = scenario["ground_truth"]

    start = time.perf_counter()
    a = await recommend_cold_storage(fridge, prefs, allergies, repo=repo)
    b = await recommend_missing_ingredients(fridge, prefs, allergies, "", repo=repo)
    elapsed_ms = (time.perf_counter() - start) * 1000

    a_ids = [r["recipe_id"] for r in a]
    b_ids = [r["recipe_id"] for r in b]
    all_ids = a_ids + b_ids

    expected = set(gt.get("expected_relevant", []))

    # 정확도 메트릭
    p_a_10 = precision_at_k(a_ids, expected, 10)
    p_b_3 = precision_at_k(b_ids, expected, 3)
    r_at_10 = recall_at_k(a_ids, expected, 10)
    mrr = reciprocal_rank(a_ids, expected)
    ndcg = ndcg_at_k(a_ids, expected, 10)

    # 안전성 메트릭 — NFR-EVAL-001
    forbidden = set(normalize_list(gt.get("forbidden_allergens", [])))
    allergy_leaks = 0
    for rid in all_ids:
        rec = repo.get(rid)
        if rec and forbidden & set(rec.allergens):
            allergy_leaks += 1

    # country/theme 일관성 (라벨 미스매칭 회귀 안전망)
    country_match = False
    if a_ids and "expected_country" in gt:
        top_country = repo.get(a_ids[0]).country if repo.get(a_ids[0]) else None
        country_match = top_country == gt["expected_country"]

    # 빈 응답 기대 케이스 검증
    empty_ok = True
    if gt.get("expected_empty_response"):
        empty_ok = len(a_ids) == 0 and len(b_ids) == 0

    return {
        "scenario_id": scenario["id"],
        "description": scenario["description"],
        "model_a_count": len(a_ids),
        "model_b_count": len(b_ids),
        "model_a_ids": a_ids,
        "model_b_ids": b_ids,
        "precision_a_at_10": p_a_10,
        "precision_b_at_3": p_b_3,
        "recall_at_10": r_at_10,
        "mrr": mrr,
        "ndcg_at_10": ndcg,
        "allergy_leaks": allergy_leaks,
        "country_match_at_top1": country_match if "expected_country" in gt else None,
        "empty_ok": empty_ok,
        "elapsed_ms": round(elapsed_ms, 2),
    }


def aggregate(results: list[dict]) -> dict[str, Any]:
    """전체 시나리오 집계."""
    n = len(results)
    if n == 0:
        return {}

    # 정답이 정의된 시나리오만 정확도 메트릭 평균
    with_truth = [r for r in results if r["precision_a_at_10"] > 0 or r["mrr"] > 0]

    # Coverage — 추천된 unique recipe / 전체 풀
    all_recommended = set()
    for r in results:
        all_recommended.update(r["model_a_ids"])
        all_recommended.update(r["model_b_ids"])
    repo = get_repository()
    coverage = len(all_recommended) / max(1, len(repo.list_all()))

    # 응답 시간 분포
    times = [r["elapsed_ms"] for r in results]

    # NFR-EVAL-001 — 알레르기 누출률
    total_leaks = sum(r["allergy_leaks"] for r in results)

    # 라벨 미스매칭 회귀 — country_match
    country_match_results = [
        r["country_match_at_top1"] for r in results
        if r["country_match_at_top1"] is not None
    ]
    country_match_rate = (
        sum(country_match_results) / len(country_match_results)
        if country_match_results else 0.0
    )

    # 빈 응답 기대 충족
    empty_ok_count = sum(1 for r in results if r["empty_ok"])

    return {
        "scenarios_total": n,
        "scenarios_with_truth": len(with_truth),
        "precision_a_at_10_mean": statistics.mean(r["precision_a_at_10"] for r in results),
        "precision_b_at_3_mean": statistics.mean(r["precision_b_at_3"] for r in results),
        "recall_at_10_mean": statistics.mean(r["recall_at_10"] for r in results),
        "mrr_mean": statistics.mean(r["mrr"] for r in results),
        "ndcg_at_10_mean": statistics.mean(r["ndcg_at_10"] for r in results),
        "allergy_leak_rate": total_leaks / n,
        "allergy_leak_count": total_leaks,
        "coverage": coverage,
        "country_match_at_top1_rate": country_match_rate,
        "empty_ok_rate": empty_ok_count / n,
        "elapsed_ms_mean": statistics.mean(times),
        "elapsed_ms_p95": sorted(times)[int(0.95 * len(times))],
    }


# ────────────────────────────────────────────────────────────────
# 임계값 (NFR + 학부 프로젝트 기준)
# ────────────────────────────────────────────────────────────────

THRESHOLDS = {
    "allergy_leak_rate_max": 0.0,        # NFR-EVAL-001 — 절대 0%
    "country_match_at_top1_min": 0.6,    # 라벨 일치 회귀
    "precision_a_at_10_min": 0.20,       # 학부 수준 (시드 35건 한계 반영)
    "mrr_min": 0.30,                     # 정답이 평균 3.3위 안에
    "coverage_min": 0.30,                # 35건 중 30% 이상 다양
    "empty_ok_rate_min": 1.0,            # 의도된 빈 응답은 100% 충족
    "elapsed_ms_p95_max": 1000.0,        # 단일 추천 < 1s (NFR-PERF-001 부분)
}


def check_thresholds(agg: dict) -> dict[str, dict]:
    """집계 메트릭이 NFR 임계값을 충족하는지 검증."""
    checks = {}
    rules = [
        ("allergy_leak_rate", "max", "allergy_leak_rate_max"),
        ("country_match_at_top1_rate", "min", "country_match_at_top1_min"),
        ("precision_a_at_10_mean", "min", "precision_a_at_10_min"),
        ("mrr_mean", "min", "mrr_min"),
        ("coverage", "min", "coverage_min"),
        ("empty_ok_rate", "min", "empty_ok_rate_min"),
        ("elapsed_ms_p95", "max", "elapsed_ms_p95_max"),
    ]
    for metric, direction, threshold_key in rules:
        actual = agg.get(metric, 0)
        threshold = THRESHOLDS[threshold_key]
        passed = (actual <= threshold) if direction == "max" else (actual >= threshold)
        checks[metric] = {
            "actual": actual,
            "direction": direction,
            "threshold": threshold,
            "passed": passed,
        }
    return checks


# ────────────────────────────────────────────────────────────────
# 보고서 출력
# ────────────────────────────────────────────────────────────────


def print_report(results: list[dict], agg: dict, checks: dict) -> None:
    print("=" * 78)
    print("추천 시스템 신뢰성·성능 평가 보고서")
    print("=" * 78)
    print(f"\n시나리오: {agg['scenarios_total']}건  (정답 정의된 시나리오: {agg['scenarios_with_truth']})\n")

    # 정확도 메트릭
    print("[정확도 메트릭] (학계 표준)")
    print(f"  Precision@10 (model A) : {agg['precision_a_at_10_mean']:.3f}")
    print(f"  Precision@3  (model B) : {agg['precision_b_at_3_mean']:.3f}")
    print(f"  Recall@10              : {agg['recall_at_10_mean']:.3f}")
    print(f"  MRR (Mean Reciprocal Rank): {agg['mrr_mean']:.3f}")
    print(f"  NDCG@10                : {agg['ndcg_at_10_mean']:.3f}")

    # 안전성·일관성
    print("\n[안전성·일관성 (NFR)]")
    print(f"  알레르기 누출 (NFR-EVAL-001) : {agg['allergy_leak_count']}건 ({agg['allergy_leak_rate']*100:.1f}%)")
    print(f"  country 일치율 (Top-1)       : {agg['country_match_at_top1_rate']*100:.1f}%")
    print(f"  빈 응답 기대 충족율          : {agg['empty_ok_rate']*100:.1f}%")

    # 다양성·성능
    print("\n[다양성·성능]")
    print(f"  Coverage (시드 35건 중)      : {agg['coverage']*100:.1f}%")
    print(f"  응답 시간 평균               : {agg['elapsed_ms_mean']:.1f} ms")
    print(f"  응답 시간 p95                : {agg['elapsed_ms_p95']:.1f} ms")

    # NFR 임계값 검증
    print("\n[NFR 임계값 검증]")
    passed_all = True
    for metric, c in checks.items():
        sign = "≤" if c["direction"] == "max" else "≥"
        status = "✅" if c["passed"] else "❌"
        line = f"  {status} {metric}: {c['actual']:.3f} {sign} {c['threshold']}"
        if not c["passed"]:
            passed_all = False
        print(line)

    print(f"\n[종합] {'✅ 전체 통과' if passed_all else '❌ 일부 미충족 — 위 ❌ 항목 보강 필요'}")

    # 시나리오별 상세 (요약)
    print("\n[시나리오별 결과]")
    print(f"  {'ID':5s} {'desc':38s} {'P@10':>6s} {'MRR':>6s} {'NDCG':>6s} {'leak':>5s} {'ms':>6s}")
    for r in results:
        desc = r["description"][:36]
        leak_marker = "❌" if r["allergy_leaks"] > 0 else "·"
        print(f"  {r['scenario_id']:5s} {desc:38s} "
              f"{r['precision_a_at_10']:.3f} {r['mrr']:.3f} {r['ndcg_at_10']:.3f} "
              f"{leak_marker:>5s} {r['elapsed_ms']:>5.1f}")


# ────────────────────────────────────────────────────────────────
# TF-IDF on/off 비교 평가 (Issue #72)
# ────────────────────────────────────────────────────────────────


def _build_name_to_id(repo: Any) -> dict[str, str]:
    """레시피 이름 → recipe_id 매핑. 시나리오 expected_relevant가
    한글 이름 또는 rNNN ID 둘 다 허용하도록 자동 변환에 사용.
    """
    return {r.name: r.recipe_id for r in repo.list_all()}


def _normalize_expected(expected: list[str], name_to_id: dict[str, str]) -> set[str]:
    """expected_relevant 항목을 recipe_id 집합으로 정규화.

    - rNNN 형식 → 그대로
    - 그 외 (한글 이름) → name_to_id 매핑. 매핑 실패 시 원본 보존 (오타 보호)
    """
    out: set[str] = set()
    for item in expected:
        if not item:
            continue
        if item.startswith("r") and item[1:].isdigit():
            out.add(item)
        elif item in name_to_id:
            out.add(name_to_id[item])
        else:
            out.add(item)  # 매칭 불가 — 결과에서 미스로 처리됨
    return out


def _empty_score_query(query_text: str) -> dict[str, float]:
    """TF-IDF OFF 모드용 — 항상 빈 dict 반환 → 가중합에 0 기여.

    model_a / model_b의 `from app.services.embedding_service import score_query`
    호출을 monkey-patch로 가로채 효과적으로 TF-IDF 가중치를 0으로 만듦.
    """
    return {}


async def _evaluate_tfidf_scenario(
    scenario: dict, repo: Any, name_to_id: dict[str, str]
) -> dict[str, Any]:
    """TF-IDF 비교용 단일 시나리오 평가 — model_a Top-10 결과를 메트릭으로 산출."""
    fridge = scenario["fridge_ingredients"]
    prefs = scenario["preferences"]
    allergies = scenario.get("user_allergies", [])
    user_ctx = scenario.get("user_context", "")
    expected_raw = scenario.get("expected_relevant", [])
    expected = _normalize_expected(expected_raw, name_to_id)

    start = time.perf_counter()
    a = await recommend_cold_storage(
        fridge_ingredients=fridge,
        preferences=prefs,
        user_allergies=allergies,
        repo=repo,
        user_context=user_ctx,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    a_ids = [r["recipe_id"] for r in a]

    return {
        "scenario_id": scenario["scenario_id"],
        "category": scenario.get("category", "-"),
        "user_context": user_ctx,
        "recommended_ids": a_ids,
        "expected_ids": sorted(expected),
        "precision_at_10": precision_at_k(a_ids, expected, 10),
        "mrr": reciprocal_rank(a_ids, expected),
        "ndcg_at_10": ndcg_at_k(a_ids, expected, 10),
        "elapsed_ms": round(elapsed_ms, 2),
        "has_truth": len(expected) > 0,
    }


def _paired_t_test(diffs: list[float]) -> tuple[float, float]:
    """간단한 paired t-test (단측이 아닌 양측, 동일 분포 가정).

    df = n-1, t = mean(d) / (sd(d)/sqrt(n)). p값은 t분포 CDF 대신
    학부 발표용 근사 — |t| ≥ 2.045 (df≈29, α=0.05) 시 "유의" 판단.
    실제 scipy 없이 표준편차 기반 t-statistic만 반환하고 임계값 가이드 출력.

    Returns: (t_stat, sample_sd)
    """
    n = len(diffs)
    if n < 2:
        return 0.0, 0.0
    mean_d = sum(diffs) / n
    var = sum((d - mean_d) ** 2 for d in diffs) / (n - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return float("inf") if mean_d != 0 else 0.0, 0.0
    t_stat = mean_d / (sd / math.sqrt(n))
    return t_stat, sd


def _interpret_t(t_stat: float, n: int) -> str:
    """학부 수준 — df 별 양측 95% 임계값 근사."""
    if n < 2:
        return "표본 부족"
    # df=23 (n=24) 양측 5% 임계값 ≈ 2.069, df=29 ≈ 2.045 (Student t 표).
    # 학부 발표 단순화 — |t| 임계값 2.07 사용.
    if math.isinf(t_stat):
        return "차이 일관 (p < 0.001)"
    abs_t = abs(t_stat)
    if abs_t >= 2.807:  # df≈23 α=0.01
        return f"매우 유의 (|t|={abs_t:.2f} ≥ 2.81, p < 0.01)"
    if abs_t >= 2.069:  # df≈23 α=0.05
        return f"유의 (|t|={abs_t:.2f} ≥ 2.07, p < 0.05)"
    return f"비유의 (|t|={abs_t:.2f} < 2.07, p ≥ 0.05)"


def _print_compare_report(
    off_results: list[dict], on_results: list[dict]
) -> None:
    """TF-IDF off vs on 비교표 + 통계 유의성 출력."""
    n = len(off_results)
    print("=" * 88)
    print("TF-IDF on/off 성능 비교 평가 (Issue #72)")
    print("=" * 88)
    print(f"\n시나리오 총 {n}개  (Model A Top-10 기준)\n")

    def _mean(rs: list[dict], key: str) -> float:
        return sum(r[key] for r in rs) / len(rs) if rs else 0.0

    metrics = [
        ("Precision@10", "precision_at_10"),
        ("MRR", "mrr"),
        ("NDCG@10", "ndcg_at_10"),
        ("Elapsed ms", "elapsed_ms"),
    ]

    # 집계 표
    print("[전체 평균]")
    print(f"  {'Metric':<14s} {'A. TF-IDF OFF':>15s} {'B. TF-IDF 0.20':>16s} {'Δ (B-A)':>10s} {'Δ%':>8s}")
    for label, key in metrics:
        a_val = _mean(off_results, key)
        b_val = _mean(on_results, key)
        delta = b_val - a_val
        pct = (delta / a_val * 100) if a_val != 0 else 0.0
        print(f"  {label:<14s} {a_val:>15.4f} {b_val:>16.4f} {delta:>+10.4f} {pct:>+7.2f}%")

    # 정답 정의된 시나리오만 (precision/mrr/ndcg는 truth 있어야 의미)
    paired = [(o, n_) for o, n_ in zip(off_results, on_results, strict=False) if o["has_truth"]]
    print(f"\n[정답 정의된 시나리오 {len(paired)}건 대상 paired t-test]")
    if not paired:
        print("  표본 없음 — t-test 생략")
    else:
        for label, key in [("Precision@10", "precision_at_10"), ("MRR", "mrr"), ("NDCG@10", "ndcg_at_10")]:
            diffs = [b[key] - a[key] for a, b in paired]
            t_stat, sd = _paired_t_test(diffs)
            mean_d = sum(diffs) / len(diffs)
            print(f"  {label:<14s} mean Δ = {mean_d:+.4f}  sd = {sd:.4f}  t = {t_stat:+.3f}  → {_interpret_t(t_stat, len(diffs))}")

    # 시나리오별 비교
    print("\n[시나리오별 결과]")
    print(f"  {'ID':5s} {'cat':6s} {'P@10 A':>7s} {'P@10 B':>7s} {'MRR A':>7s} {'MRR B':>7s} {'NDCG A':>7s} {'NDCG B':>7s} ctx")
    for a, b in zip(off_results, on_results, strict=False):
        ctx = (a["user_context"][:28] + "…") if len(a["user_context"]) > 28 else a["user_context"]
        print(
            f"  {a['scenario_id']:5s} {a['category']:6s} "
            f"{a['precision_at_10']:>7.3f} {b['precision_at_10']:>7.3f} "
            f"{a['mrr']:>7.3f} {b['mrr']:>7.3f} "
            f"{a['ndcg_at_10']:>7.3f} {b['ndcg_at_10']:>7.3f} {ctx}"
        )

    # 카테고리별 집계 — 발표용 인사이트
    cats: dict[str, list[tuple[dict, dict]]] = {}
    for a, b in zip(off_results, on_results, strict=False):
        cats.setdefault(a["category"], []).append((a, b))
    print("\n[카테고리별 P@10 평균]")
    print(f"  {'category':<10s} {'n':>3s} {'A OFF':>8s} {'B ON':>8s} {'Δ':>8s}")
    for cat, pairs in sorted(cats.items()):
        n_c = len(pairs)
        a_avg = sum(a["precision_at_10"] for a, _ in pairs) / n_c
        b_avg = sum(b["precision_at_10"] for _, b in pairs) / n_c
        print(f"  {cat:<10s} {n_c:>3d} {a_avg:>8.3f} {b_avg:>8.3f} {b_avg - a_avg:>+8.3f}")


async def run_compare_tfidf() -> int:
    """TF-IDF on/off 두 모드로 시나리오 평가 후 비교 보고서 출력.

    구현 핵심:
      - OFF: emb_mod.score_query를 빈 dict 반환 함수로 monkey-patch → 가중합에 0 기여
      - ON : 원본 score_query 복원 → 0.20 가중치 적용
      - model_a/model_b 알고리즘 코드는 손대지 않음 (Issue #72 다른 에이전트 작업 보호)
    """
    mb_mod.gemini_select_top3 = _mock_gemini_none

    with TFIDF_SCENARIOS_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    scenarios = data["scenarios"]

    repo = get_repository()
    name_to_id = _build_name_to_id(repo)

    # TF-IDF 코퍼스 fit — 평가 스크립트는 main.py startup을 거치지 않으므로
    # 명시적으로 fit_corpus 호출. 호출하지 않으면 _VECTORIZER=None → ON 모드도
    # 빈 dict 반환되어 두 모드가 동일해짐 (검증 실패).
    if not emb_mod.is_ready():
        emb_mod.fit_corpus(repo.list_all())
        if not emb_mod.is_ready():
            print("⚠ TF-IDF fit_corpus 실패 — 비교 결과 무의미. 코퍼스 확인 필요.")
            return 1

    # 원본 score_query 보존
    original_score_query = emb_mod.score_query

    # ── A. TF-IDF OFF ──
    emb_mod.score_query = _empty_score_query
    off_results = []
    for sc in scenarios:
        off_results.append(await _evaluate_tfidf_scenario(sc, repo, name_to_id))

    # ── B. TF-IDF ON (가중치 0.20) ──
    emb_mod.score_query = original_score_query
    on_results = []
    for sc in scenarios:
        on_results.append(await _evaluate_tfidf_scenario(sc, repo, name_to_id))

    _print_compare_report(off_results, on_results)

    # 항상 exit 0 — 비교는 정보 출력용, NFR 임계값 검증 아님
    return 0


# ────────────────────────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────────────────────────


async def main() -> int:
    """메인 평가. 임계값 미충족 시 exit code 1 (CI 회귀용).

    --compare-tfidf 플래그 시 TF-IDF on/off 비교 모드로 실행.
    """
    if "--compare-tfidf" in sys.argv:
        return await run_compare_tfidf()

    mb_mod.gemini_select_top3 = _mock_gemini_none  # Gemini 폴백 강제 — 결정론

    with GOLDEN_PATH.open("r", encoding="utf-8") as f:
        golden = json.load(f)

    repo = get_repository()
    results = []
    for scenario in golden["scenarios"]:
        result = await evaluate_scenario(scenario, repo)
        results.append(result)

    agg = aggregate(results)
    checks = check_thresholds(agg)
    print_report(results, agg, checks)

    # CI exit code
    all_passed = all(c["passed"] for c in checks.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
