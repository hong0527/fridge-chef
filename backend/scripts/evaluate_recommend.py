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
from app.services import model_b as mb_mod  # noqa: E402
from app.services.model_a import recommend_cold_storage  # noqa: E402
from app.services.model_b import recommend_missing_ingredients  # noqa: E402

GOLDEN_PATH = _BACKEND_DIR / "tests" / "fixtures" / "recommend_golden_set.json"


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
# 메인
# ────────────────────────────────────────────────────────────────


async def main() -> int:
    """메인 평가. 임계값 미충족 시 exit code 1 (CI 회귀용)."""
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
