"""추천 시스템 골든셋 회귀 테스트 — 5가지 실사용 시나리오.

시나리오 (시드 35개 기준):
A. 한식 매운 음식 + 알레르기 없음 → model_a/b 1건 이상
B. 양식 선호 + 우유 알레르기 → 치즈 들어간 레시피 0건
C. 초보 + 저칼로리 → 결과의 difficulty_level <= 2
D. 한식 선호인데 양식이 상위로 → ordinal 인코딩 결함 노출
E. 빈 냉장고 → 빈 리스트 안전 반환

알려진 결함은 xfail로 마킹.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.synonym_map import normalize_list
from app.models.recipe_repository import get_repository
from app.services.recommend_service import recommend_dual

_BASE_PREFS = {
    "spicy": 3,
    "difficulty": "초보",
    "max_cook_min": 60,
    "country": "한식",
    "food_type": "메인요리",
    "diet": False,
}


# ────────────────────────────────────────────────────────────────
# 시나리오 A: 한식 매운 + 알레르기 없음
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="CRITICAL: contains_all + 시드 양념 비일관성으로 평범한 7개 입력에 결과 ≤ 2건",
    strict=False,
)
async def test_scenario_a_korean_spicy_yields_results(mock_gemini_fail: Any) -> None:
    """한식 매운 음식 선호 + 평범한 한식 재료 7개 → model_a 3건 이상, model_b 1건 이상."""
    repo = get_repository()
    prefs = {**_BASE_PREFS, "spicy": 4, "country": "한식"}
    result = await recommend_dual(
        fridge_ingredients=["양파", "마늘", "계란", "김치", "돼지고기", "두부", "대파"],
        preferences=prefs,
        user_allergies=[],
        user_context="매콤한 점심",
        repo=repo,
    )
    assert len(result["model_a"]) >= 3, (
        f"한식 7개 입력에 model_a {len(result['model_a'])}건. 시드 양념 결함. "
        f"추천: {[r['recipe_id'] for r in result['model_a']]}"
    )
    assert len(result["model_b"]) >= 1, "model_b 빈 응답"


# ────────────────────────────────────────────────────────────────
# 시나리오 B: 양식 선호 + 우유 알레르기 → 치즈 차단
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="CRITICAL NFR-EVAL-001: expand_allergies 미연결 → '우유' 카테고리가 '치즈' 함유 레시피 차단 못 함",
    strict=False,
)
async def test_scenario_b_milk_allergy_blocks_cheese_recipes(
    mock_gemini_fail: Any,
) -> None:
    """우유 알레르기 사용자에게 치즈 든 레시피(r017 샐러드, r018 파스타 등) 차단."""
    repo = get_repository()
    prefs = {**_BASE_PREFS, "country": "양식"}
    result = await recommend_dual(
        fridge_ingredients=["면", "올리브유", "마늘", "치즈", "토마토", "양파"],
        preferences=prefs,
        user_allergies=["우유"],
        user_context="",
        repo=repo,
    )
    cheese_recipes = {"r017", "r018", "r020"}  # 시드 중 치즈/우유 알레르겐 있는 레시피
    leaked = [
        r["recipe_id"]
        for r in result["model_a"] + result["model_b"]
        if r["recipe_id"] in cheese_recipes
    ]
    assert not leaked, (
        f"우유 알레르기인데 치즈 들어간 레시피 노출: {leaked}. "
        f"expand_allergies('우유') → ['치즈', '버터', '크림', ...] 호출 필요."
    )


# ────────────────────────────────────────────────────────────────
# 시나리오 C: 초보 + 저칼로리 → difficulty_level <= 2
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scenario_c_beginner_easy_recipes_only(mock_gemini_fail: Any) -> None:
    """난이도 '초보' 선호 + max_cook_min=20 → Top-5의 difficulty_level <=2 비율 ≥ 60%.

    PR #40 Stratified retrieval로 country+theme+diff 일치 → 일치 country만 → base pool
    순으로 fallback이 있어 후순위에 diff=3 일부 포함 가능. 가중합 score가 일치 후보를
    상위에 두므로 Top-5의 60% 이상은 diff <= 2 보장.
    """
    repo = get_repository()
    prefs = {**_BASE_PREFS, "difficulty": "초보", "max_cook_min": 20, "diet": True}
    result = await recommend_dual(
        fridge_ingredients=["양파", "당근", "버섯", "간장", "마늘"],
        preferences=prefs,
        user_allergies=[],
        user_context="",
        repo=repo,
    )
    top5 = result["model_a"][:5]
    if not top5:
        pytest.skip("contains_all 통과 후보 부족 (SEED 35건 한계)")
    easy_count = sum(1 for r in top5 if r["difficulty_level"] <= 2)
    assert easy_count >= len(top5) * 0.6, (
        f"Top-{len(top5)} 중 초보·중급 {easy_count}건 < 60% — stratified 미작동"
    )


# ────────────────────────────────────────────────────────────────
# 시나리오 D: country 선호 반영 — ordinal 인코딩 결함 노출
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="CRITICAL: country를 ordinal(0.2~1.0)로 인코딩해 코사인 거리에 넣음 → "
    "'한식' 선호인데 양식이 상위에 옴. one-hot 또는 동치 매칭으로 교체 필요.",
    strict=False,
)
async def test_scenario_d_country_preference_respected(mock_gemini_fail: Any) -> None:
    """'한식'·메인요리 선호에서 model_a 결과의 첫 후보가 한식이어야 함."""
    repo = get_repository()
    prefs = {**_BASE_PREFS, "country": "한식", "food_type": "메인요리"}
    # 양식/한식 모두 통과할 수 있는 입력
    result = await recommend_dual(
        fridge_ingredients=["면", "올리브유", "마늘", "계란", "대파", "소금", "간장", "두부"],
        preferences=prefs,
        user_allergies=[],
        user_context="",
        repo=repo,
    )
    if len(result["model_a"]) < 2:
        pytest.skip(f"contains_all 결함으로 후보 부족. 추천: {result['model_a']}")
    repo_index = {r.recipe_id: r for r in repo.list_all()}
    first_country = repo_index[result["model_a"][0]["recipe_id"]].country
    assert first_country == "kr", (
        f"'한식' 선호인데 첫 추천 country={first_country}. "
        f"ordinal 인코딩(kr=0.2, west=0.8) 왜곡."
    )


# ────────────────────────────────────────────────────────────────
# 시나리오 E: 빈 냉장고 안전성
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scenario_e_empty_fridge_returns_empty(mock_gemini_fail: Any) -> None:
    """빈 냉장고는 예외 없이 빈 리스트 반환."""
    repo = get_repository()
    result = await recommend_dual(
        fridge_ingredients=[],
        preferences=_BASE_PREFS,
        user_allergies=[],
        user_context="",
        repo=repo,
    )
    assert result["model_a"] == [], f"빈 냉장고에 model_a 추천: {result['model_a']}"
    # model_b도 빈 냉장고면 missing>5라 후보 0건 → 빈 리스트
    assert result["model_b"] == [], f"빈 냉장고에 model_b 추천: {result['model_b']}"


# ────────────────────────────────────────────────────────────────
# 시나리오 F (보너스): 알레르기 정규화 일치 (정상 매핑)
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_normalized_allergy_keyword_works(mock_gemini_fail: Any) -> None:
    """'달걀' 입력 시 synonym_map으로 '계란'으로 정규화되어 차단되어야 함."""
    repo = get_repository()
    result = await recommend_dual(
        fridge_ingredients=["계란", "대파", "소금"],
        preferences=_BASE_PREFS,
        user_allergies=["달걀"],  # 정규화 대상
        user_context="",
        repo=repo,
    )
    egg_recipes = {"r001", "r009", "r010", "r013", "r020", "r027", "r028", "r030", "r033", "r034"}
    leaked = [
        r["recipe_id"]
        for r in result["model_a"] + result["model_b"]
        if r["recipe_id"] in egg_recipes
    ]
    assert not leaked, f"'달걀' 알레르기인데 계란 레시피 노출: {leaked}"


# 정규화 보존 검증 (도움 함수 회귀)
def test_normalize_list_preserves_order_for_allergies() -> None:
    out = normalize_list(["달걀", "쪽파", "양조간장"])
    assert out == ["계란", "대파", "간장"], f"정규화 결과 다름: {out}"
