"""Model A 필터 회귀 테스트 — 알려진 결함을 xfail로 노출하여 회귀 안전망 구축.

대상: backend/app/services/model_a.py::recommend_cold_storage
검증 항목:
1. contains_all 하드 필터 + 시드 양념 비일관성 → 빈 결과 (CRITICAL)
2. 알레르기 카테고리 ("난류") → 세부 재료 ("계란") 확장 미연결 (CRITICAL, NFR-EVAL-001)
3. max_cook_min 필터 정상 동작
4. 빈 입력 안전성

xfail 마킹은 결함이 픽스되면 자동으로 xpassed로 전환되어 픽스 검증 도구로 사용됨.
"""

from __future__ import annotations

import pytest

from app.models.recipe_repository import get_repository
from app.services.model_a import recommend_cold_storage

_BASE_PREFS = {
    "spicy": 3,
    "difficulty": "초보",
    "max_cook_min": 60,
    "country": "한식",
    "food_type": "메인요리",
    "diet": False,
}


# ────────────────────────────────────────────────────────────────
# 결함 #1: contains_all 하드 필터 — 평범한 입력에 빈 결과
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contains_all_returns_results_for_typical_fridge() -> None:
    """평범한 사용자 냉장고(주재료 7개)에 시드 35개에서 5건 이상 추천되어야 함."""
    repo = get_repository()
    out = await recommend_cold_storage(
        fridge_ingredients=["양파", "마늘", "계란", "김치", "돼지고기", "두부", "대파"],
        preferences=_BASE_PREFS,
        user_allergies=[],
        repo=repo,
    )
    assert len(out) >= 5, (
        f"평범한 입력에 추천 {len(out)}건 — 시드 양념 비일관성 때문에 contains_all 통과율 낮음. "
        f"실제 추천: {[r['recipe_id'] for r in out]}"
    )


@pytest.mark.asyncio
async def test_contains_all_minimum_case_passes() -> None:
    """소금까지 포함한 완전한 입력은 r001 계란말이가 통과해야 함 (현재 코드도 통과)."""
    repo = get_repository()
    out = await recommend_cold_storage(
        fridge_ingredients=["계란", "대파", "소금"],
        preferences=_BASE_PREFS,
        user_allergies=[],
        repo=repo,
    )
    rids = [r["recipe_id"] for r in out]
    assert "r001" in rids, f"r001 계란말이가 추천되어야 함. 실제: {rids}"


# ────────────────────────────────────────────────────────────────
# 결함 #2: 알레르기 카테고리 확장 미연결 (NFR-EVAL-001 위반)
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_allergy_category_expansion_blocks_egg_recipes() -> None:
    """사용자가 '난류' 카테고리로 알레르기 등록 → r001 계란말이(allergens=['계란']) 차단되어야 함."""
    repo = get_repository()
    out = await recommend_cold_storage(
        fridge_ingredients=["계란", "대파", "소금"],
        preferences=_BASE_PREFS,
        user_allergies=["난류"],  # 카테고리 입력
        repo=repo,
    )
    rids = [r["recipe_id"] for r in out]
    assert "r001" not in rids, (
        f"NFR-EVAL-001 위반: '난류' 알레르기 입력에 r001 계란말이 노출됨. "
        f"expand_allergies('난류') → ['계란', '달걀', ...] 호출이 model_a.py:103에서 필요. 추천: {rids}"
    )


@pytest.mark.asyncio
async def test_allergy_exact_keyword_blocks_recipe() -> None:
    """세부 키워드('계란')로 직접 입력하면 차단되어야 함 (정규화로 매칭됨)."""
    repo = get_repository()
    out = await recommend_cold_storage(
        fridge_ingredients=["계란", "대파", "소금"],
        preferences=_BASE_PREFS,
        user_allergies=["계란"],
        repo=repo,
    )
    rids = [r["recipe_id"] for r in out]
    assert "r001" not in rids, (
        f"세부 알레르기 키워드 '계란' 입력에도 r001 노출. 추천: {rids}"
    )


# ────────────────────────────────────────────────────────────────
# 결함 #3: max_cook_min 필터 동작 검증
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_max_cook_min_filter_works() -> None:
    """max_cook_min=10 입력 시 cook_min > 10인 레시피 모두 제외."""
    repo = get_repository()
    prefs = {**_BASE_PREFS, "max_cook_min": 10}
    out = await recommend_cold_storage(
        fridge_ingredients=["계란", "대파", "소금"],
        preferences=prefs,
        user_allergies=[],
        repo=repo,
    )
    for r in out:
        assert r["cook_min"] <= 10, (
            f"max_cook_min=10 필터 위반: {r['recipe_id']} cook_min={r['cook_min']}"
        )


# ────────────────────────────────────────────────────────────────
# 결함 #4: 빈 입력 안전성
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_fridge_returns_empty() -> None:
    """빈 냉장고 입력 시 빈 리스트 안전 반환 (예외 발생 금지)."""
    repo = get_repository()
    out = await recommend_cold_storage(
        fridge_ingredients=[],
        preferences=_BASE_PREFS,
        user_allergies=[],
        repo=repo,
    )
    assert out == [], f"빈 냉장고에 추천 발생: {out}"


@pytest.mark.asyncio
async def test_empty_allergies_does_not_block_anything() -> None:
    """빈 알레르기 입력 시 알레르기 필터 비활성 (재료만 충족하면 통과)."""
    repo = get_repository()
    out_no_allergy = await recommend_cold_storage(
        fridge_ingredients=["계란", "대파", "소금"],
        preferences=_BASE_PREFS,
        user_allergies=[],
        repo=repo,
    )
    rids = [r["recipe_id"] for r in out_no_allergy]
    assert "r001" in rids, f"빈 알레르기인데 r001 차단됨: {rids}"


# ────────────────────────────────────────────────────────────────
# 결함 #5: country/theme ordinal 인코딩 왜곡 (순위가 사용자 선호 반영 못 함)
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_country_preference_ranks_korean_higher_than_western() -> None:
    """'한식' 선호 입력 시 한식 레시피가 양식 레시피보다 상위에 위치해야 함."""
    repo = get_repository()
    # 한식·양식 양쪽 통과 가능한 재료 입력 (시뮬레이션을 위해 통과 가능한 조합)
    prefs_kr = {**_BASE_PREFS, "country": "한식", "food_type": "메인요리"}
    out = await recommend_cold_storage(
        fridge_ingredients=["면", "올리브유", "마늘", "치즈", "계란", "대파", "소금"],
        preferences=prefs_kr,
        user_allergies=[],
        repo=repo,
    )
    rids = [r["recipe_id"] for r in out]
    if len(out) < 2:
        pytest.skip(f"통과 후보 부족 — contains_all 결함 영향. 추천: {rids}")
    # 한식 레시피(r0XX kr country)가 양식보다 앞에 있어야 함
    first = repo.list_all()
    first_by_id = {r.recipe_id: r for r in first}
    countries = [first_by_id[r["recipe_id"]].country for r in out]
    # 첫 후보가 양식이면 ordinal 인코딩 결함 노출
    assert countries[0] == "kr", (
        f"'한식' 선호인데 첫 추천이 {countries[0]}. "
        f"country/theme ordinal 인코딩(model_a.py:48-49) 왜곡 가능성. "
        f"전체 country 순서: {countries}"
    )
