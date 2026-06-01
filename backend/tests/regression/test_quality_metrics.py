"""추천 시스템 품질 메트릭 회귀 테스트 (NFR + 학계 표준).

scripts/evaluate_recommend.py와 동일 로직을 pytest로 자동화하여 CI에서
품질 임계값 회귀를 차단한다. 알고리즘·시드·라벨 변경 시 메트릭이 하락하면
CI 실패.

참조 메트릭 (Shani & Gunawardana 2011, Microsoft Recommenders):
- Precision@K, Recall@K, MRR, NDCG@K
- Constraint Satisfaction Rate (알레르기) — Hard gate
- Catalog Coverage
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

import pytest

from app.core.synonym_map import normalize_list
from app.models.recipe_repository import get_repository
from app.services import model_b as mb_mod
from app.services.model_a import recommend_cold_storage
from app.services.model_b import recommend_missing_ingredients

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "recommend_golden_set.json"


# ────────────────────────────────────────────────────────────────
# 메트릭 정의 (학계 표준)
# ────────────────────────────────────────────────────────────────


def precision_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    if k <= 0 or not recommended:
        return 0.0
    top_k = recommended[:k]
    hits = sum(1 for r in top_k if r in relevant)
    return hits / min(k, len(top_k))


def reciprocal_rank(recommended: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 1.0
    for i, r in enumerate(recommended):
        if r in relevant:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(recommended: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 1.0
    dcg = 0.0
    for i, r in enumerate(recommended[:k]):
        if r in relevant:
            dcg += 1.0 / math.log2(i + 2)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


# ────────────────────────────────────────────────────────────────
# 픽스처
# ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def golden_scenarios() -> list[dict]:
    """골든셋 30개 시나리오 로드."""
    with GOLDEN_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)["scenarios"]


@pytest.fixture
def gemini_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gemini 폴백 강제 — 결정론 평가."""
    async def _none(candidates, user_context):
        return None
    monkeypatch.setattr(mb_mod, "gemini_select_top3", _none)


# ────────────────────────────────────────────────────────────────
# 헬퍼: 모든 시나리오 실행
# ────────────────────────────────────────────────────────────────


async def _run_all_scenarios(scenarios: list[dict]) -> list[dict[str, Any]]:
    repo = get_repository()
    results = []
    for scenario in scenarios:
        a = await recommend_cold_storage(
            scenario["fridge"], scenario["preferences"], scenario["allergies"], repo=repo,
        )
        b = await recommend_missing_ingredients(
            scenario["fridge"], scenario["preferences"], scenario["allergies"], "", repo=repo,
        )
        a_ids = [r["recipe_id"] for r in a]
        b_ids = [r["recipe_id"] for r in b]
        gt = scenario["ground_truth"]
        expected = set(gt.get("expected_relevant", []))
        forbidden = set(normalize_list(gt.get("forbidden_allergens", [])))

        leaks = 0
        for rid in a_ids + b_ids:
            rec = repo.get(rid)
            if rec and forbidden & set(rec.allergens):
                leaks += 1

        results.append({
            "id": scenario["id"],
            "a_ids": a_ids,
            "b_ids": b_ids,
            "expected": expected,
            "leaks": leaks,
            "gt": gt,
            "scenario": scenario,
        })
    return results


# ────────────────────────────────────────────────────────────────
# 회귀 테스트 — 학계 표준 메트릭
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_csr_allergy_leak_zero(golden_scenarios, gemini_off) -> None:
    """NFR-EVAL-001 Hard Gate — 알레르기 누출 0건 (Constraint Satisfaction Rate = 1.0)."""
    results = await _run_all_scenarios(golden_scenarios)
    total_leaks = sum(r["leaks"] for r in results)
    leaked_scenarios = [r["id"] for r in results if r["leaks"] > 0]
    assert total_leaks == 0, (
        f"알레르기 누출 {total_leaks}건 발견. 시나리오: {leaked_scenarios}. "
        f"NFR-EVAL-001 (알레르기 0%) 위반."
    )


@pytest.mark.asyncio
async def test_precision_at_10_meets_threshold(golden_scenarios, gemini_off) -> None:
    """학부 수준 Precision@10 평균 ≥ 0.20 (목표: 0.40+)."""
    results = await _run_all_scenarios(golden_scenarios)
    precisions = [precision_at_k(r["a_ids"], r["expected"], 10) for r in results]
    mean_p = statistics.mean(precisions)
    assert mean_p >= 0.20, (
        f"Precision@10 = {mean_p:.3f} < 0.20. 추천 정확도 저하 회귀."
    )


@pytest.mark.asyncio
async def test_mrr_meets_threshold(golden_scenarios, gemini_off) -> None:
    """MRR ≥ 0.30 — 정답이 평균 3위 이내에 등장."""
    results = await _run_all_scenarios(golden_scenarios)
    mrrs = [reciprocal_rank(r["a_ids"], r["expected"]) for r in results]
    mean_mrr = statistics.mean(mrrs)
    assert mean_mrr >= 0.30, (
        f"MRR = {mean_mrr:.3f} < 0.30. 정답이 상위에 오지 않음."
    )


@pytest.mark.asyncio
async def test_ndcg_at_10_meets_threshold(golden_scenarios, gemini_off) -> None:
    """NDCG@10 ≥ 0.50 — 순위 가중 정확도 (Shani & Gunawardana 2011)."""
    results = await _run_all_scenarios(golden_scenarios)
    ndcgs = [ndcg_at_k(r["a_ids"], r["expected"], 10) for r in results]
    mean_ndcg = statistics.mean(ndcgs)
    assert mean_ndcg >= 0.50, (
        f"NDCG@10 = {mean_ndcg:.3f} < 0.50. 순위 품질 저하."
    )


@pytest.mark.asyncio
async def test_country_match_at_top1(golden_scenarios, gemini_off) -> None:
    """라벨 미스매칭 회귀 — country 선호와 Top-1 추천의 일치율 ≥ 60%."""
    results = await _run_all_scenarios(golden_scenarios)
    repo = get_repository()
    matches = []
    for r in results:
        if "expected_country" not in r["gt"]:
            continue
        if not r["a_ids"]:
            continue
        top = repo.get(r["a_ids"][0])
        matches.append(top.country == r["gt"]["expected_country"])

    if matches:
        rate = sum(matches) / len(matches)
        assert rate >= 0.60, (
            f"country 일치율 = {rate*100:.1f}% < 60%. "
            f"PreferenceWizard 라벨 미스매칭 회귀 의심."
        )


@pytest.mark.asyncio
async def test_catalog_coverage_min(golden_scenarios, gemini_off) -> None:
    """Catalog Coverage ≥ 30% — 시드 35건 중 다양하게 추천."""
    results = await _run_all_scenarios(golden_scenarios)
    all_recommended = set()
    for r in results:
        all_recommended.update(r["a_ids"])
        all_recommended.update(r["b_ids"])
    repo = get_repository()
    coverage = len(all_recommended) / max(1, len(repo.list_all()))
    assert coverage >= 0.30, (
        f"Coverage = {coverage*100:.1f}% < 30%. 추천 다양성 부족."
    )


@pytest.mark.asyncio
async def test_empty_response_for_empty_fridge(golden_scenarios, gemini_off) -> None:
    """빈 냉장고 시나리오는 빈 응답을 반환해야 함."""
    empty_scenarios = [s for s in golden_scenarios
                       if s["ground_truth"].get("expected_empty_response")]
    assert empty_scenarios, "골든셋에 빈 응답 케이스 누락"
    results = await _run_all_scenarios(empty_scenarios)
    for r in results:
        assert len(r["a_ids"]) == 0 and len(r["b_ids"]) == 0, (
            f"{r['id']}: 빈 입력에 추천 발생. a={r['a_ids']} b={r['b_ids']}"
        )


@pytest.mark.asyncio
async def test_model_a_and_b_produce_different_results(
    golden_scenarios, gemini_off,
) -> None:
    """두 모델이 같은 입력에 서로 다른 결과를 내야 함 (코사인 vs 복합점수)."""
    results = await _run_all_scenarios(golden_scenarios[:5])  # 빠른 검증용 5개
    differing = 0
    for r in results:
        if r["a_ids"] and r["b_ids"] and r["a_ids"] != r["b_ids"]:
            differing += 1
    assert differing >= 2, (
        f"5개 시나리오 중 {differing}개만 model_a≠model_b. "
        f"두 모델이 사실상 동일 결과 — 알고리즘 분리 결함 의심."
    )
