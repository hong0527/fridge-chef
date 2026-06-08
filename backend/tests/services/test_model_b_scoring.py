"""Model B 점수·Gemini 검증 회귀 테스트.

대상: backend/app/services/model_b.py::recommend_missing_ingredients
검증 항목:
1. mock_gemini_fail → final_score Top-3 폴백 (정상 동작 확인)
2. mock_gemini_success → citation_ids 검증 통과 (정상 동작 확인)
3. Gemini 화이트리스트 밖 ID 차단 (CRITICAL: gemini_client.py:128 자기인용 폴백 때문에 차단 안 될 수 있음 → xfail)
4. missing_count > MISSING_INGREDIENTS_MAX 후보 제외
5. recommend_service.gather 타임아웃 시 model_a까지 폐기되는 구조적 결함 (CRITICAL)
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.models.recipe_repository import get_repository
from app.services import model_b as mb_mod
from app.services.model_b import recommend_missing_ingredients
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
# 결함 #1 (POSITIVE): mock_gemini_fail 폴백 동작
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gemini_fail_fallback_returns_top_by_final_score(
    mock_gemini_fail: Any,
) -> None:
    """Gemini 실패(None) 시 final_score Top-3 폴백으로 결과 반환."""
    repo = get_repository()
    out = await recommend_missing_ingredients(
        fridge_ingredients=["계란", "대파", "소금", "두부", "마늘"],
        preferences=_BASE_PREFS,
        user_allergies=[],
        user_context="",
        repo=repo,
    )
    # 폴백이라도 1개 이상 반환되어야 함
    assert len(out) >= 1, "Gemini 실패 폴백에서 결과 0건"
    for r in out:
        # critic F3 빈 카드 차단 — Gemini 폴백 시 결정론 한국어 문장 보장.
        assert r["reason"], (
            f"폴백이라도 결정론 reason 자동 생성. 실제: '{r['reason']}'"
        )
        assert "보유" in r["reason"] or "활용" in r["reason"]


# ────────────────────────────────────────────────────────────────
# 결함 #2 (POSITIVE): mock_gemini_success citation 검증 통과
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gemini_success_attaches_reasons(
    mock_gemini_success: Any,
) -> None:
    """Gemini 성공 모킹 시 reason 문자열이 채워짐."""
    repo = get_repository()
    out = await recommend_missing_ingredients(
        fridge_ingredients=["계란", "대파", "소금", "두부", "마늘"],
        preferences=_BASE_PREFS,
        user_allergies=[],
        user_context="와인과 곁들이고 싶어",
        repo=repo,
    )
    assert 1 <= len(out) <= 3
    for r in out:
        assert r["reason"].endswith("Gemini 추천 이유"), (
            f"reason 미설정: {r['reason']!r}"
        )


# ────────────────────────────────────────────────────────────────
# 결함 #3 (CRITICAL): 화이트리스트 밖 recipe_id 차단 결함
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="CRITICAL NFR-EVAL-002: gemini_client.py:128 setdefault('citation_ids', selected)가 "
    "model_b의 자기인용 차단 로직(model_b.py:99 주석)을 무력화. "
    "화이트리스트 밖 ID를 selected로 받으면 폴백으로 정상 ID가 채워지긴 하나 "
    "selected_ids 채움 로직(model_b.py:111-116)이 미검증 후보를 무조건 추가하는 문제도 동시 노출.",
    strict=False,
)
async def test_gemini_hallucinated_ids_are_blocked_not_replaced_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gemini가 화이트리스트 밖 recipe_id를 반환하면 NFR-EVAL-002에 따라 검증 실패로 분류되어야 함.

    현재 model_b는 폴백으로 final_score Top-3를 무조건 채워 넣어서 사용자에게는
    정상 응답처럼 보이지만, 운영 측은 Gemini 환각률 측정이 불가능.
    이 테스트는 '폴백 발생 시 meta 필드로 알림이 있어야 함' 요구를 반영.
    """
    repo = get_repository()

    async def _hallucinate(_candidates: list[dict], _user_context: str) -> dict[str, Any]:
        return {
            "selected": ["FAKE_001", "FAKE_002", "FAKE_003"],
            "reasons": ["가짜1", "가짜2", "가짜3"],
            "citation_ids": ["FAKE_001", "FAKE_002", "FAKE_003"],
        }

    monkeypatch.setattr(mb_mod, "gemini_select_top3", _hallucinate)
    out = await recommend_missing_ingredients(
        fridge_ingredients=["계란", "대파", "소금", "두부", "마늘"],
        preferences=_BASE_PREFS,
        user_allergies=[],
        user_context="",
        repo=repo,
    )
    # 환각 ID가 응답에 노출되면 안 됨 (이건 이미 model_b 화이트리스트 검증으로 차단됨)
    rids = [r["recipe_id"] for r in out]
    for rid in rids:
        assert rid in repo.whitelist_ids(), f"환각 ID 노출: {rid}"
    # 환각 발생을 알릴 수단(reason="" 등)이 있어야 함 (현재는 폴백이 silent)
    has_meta_indicator = any(
        not r.get("reason") for r in out
    )
    assert has_meta_indicator, (
        "Gemini 환각 폴백이 silent — 운영 메트릭으로 감지 불가. "
        "model_b 응답에 verified=false 또는 reason='' 표시 필요."
    )


# ────────────────────────────────────────────────────────────────
# 결함 #4: MISSING_INGREDIENTS_MAX 초과 후보 제외
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_missing_max_filter_excludes_far_recipes(
    mock_gemini_fail: Any,
) -> None:
    """냉장고에 1개만 있고 부족재료 max(5) 초과인 레시피는 후보에서 제외."""
    repo = get_repository()
    # 냉장고에 "계란"만 있음 → 거의 모든 레시피의 missing > 5
    out = await recommend_missing_ingredients(
        fridge_ingredients=["계란"],
        preferences=_BASE_PREFS,
        user_allergies=[],
        user_context="",
        repo=repo,
    )
    for r in out:
        assert len(r["missing"]) <= 5, (
            f"missing>5인 레시피 통과: {r['recipe_id']} missing={r['missing']}"
        )


# ────────────────────────────────────────────────────────────────
# 결함 #5 (CRITICAL): recommend_service의 gather 타임아웃 시 model_a까지 폐기
# ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gemini_slow_does_not_kill_model_a(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """# NFR-REL-001 — Gemini 느려도 model_a 결과는 정상 반환되어야 함."""
    repo = get_repository()

    async def _slow_gemini(candidates: list[dict], user_context: str) -> Any:
        await asyncio.sleep(15)  # recommend_timeout_s(10) 초과 강제
        return None

    monkeypatch.setattr(mb_mod, "gemini_select_top3", _slow_gemini)

    # RECOMMEND_TIMEOUT_S=10초이지만 테스트에서는 1초로 강제하기 위해 monkeypatch.setenv는
    # config가 frozen이라 무용. 대신 짧은 sleep으로 시뮬레이션.
    result = await recommend_dual(
        fridge_ingredients=["계란", "대파", "소금"],
        preferences=_BASE_PREFS,
        user_allergies=[],
        user_context="",
        repo=repo,
    )
    # model_a는 결과가 있어야 함 (model_b가 느려도)
    assert len(result["model_a"]) >= 1, (
        "Gemini 타임아웃 시 model_a까지 폐기됨. "
        "recommend_service.py에서 두 모델을 독립 try/except로 분리 필요."
    )
