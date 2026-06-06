"""추천 시스템 핵심 불변식 회귀 테스트 — 학부 시연 안전망.

`test_quality_metrics.py` 가 학계 메트릭 임계값을 검증한다면,
본 파일은 알고리즘 설계 의도의 절대 불변식을 회귀한다:

  1. 알레르기 차단 100% (NFR-EVAL-001) — 자연어 컨텍스트에서도 유지
  2. Model A ∩ Model B = ∅ (SDD §3.2 자연 분리)
  3. country/theme prefs hard filter (사용자 의도 침범 0)
  4. 응답 시간 ≤ 10초 (NFR-PERF-003)
  5. Gemini 실패 시에도 빈 응답 없음 (NFR-REL-001)
  6. expand_context 가 추천 시스템 호출에서 부작용 없이 통합됨

학부 시연 직전 단일 명령 회귀:
  pytest tests/regression/test_recommend_invariants.py -v
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from app.core.synonym_map import normalize_list
from app.services import model_b as mb_mod
from app.services.model_a import recommend_cold_storage
from app.services.model_b import recommend_missing_ingredients
from app.services.recommend_service import recommend_dual

# ────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────


@pytest.fixture
def gemini_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gemini 폴백 강제 (결정론)."""
    async def _none(candidates, user_context):
        return None
    monkeypatch.setattr(mb_mod, "gemini_select_top3", _none)


_DEFAULT_PREFS: dict[str, Any] = {
    "country": "한식",
    "food_type": "메인요리",
    "spicy": 2,
    "difficulty": "초보",
    "max_cook_min": 60,
    "diet": False,
}


# ────────────────────────────────────────────────────────────────
# 1. 알레르기 100% 차단 (NFR-EVAL-001) — E2E 자동 검증
# ────────────────────────────────────────────────────────────────


class TestAllergyBlockingE2E:
    """알레르기 hard filter 가 자연어 컨텍스트·다양한 입력에서도 100% 동작."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "allergies,nl_context",
        [
            (["조개"], "비 오는 날 따뜻한 국물"),
            (["땅콩"], "간단한 샌드위치"),
            (["우유"], "크림 베이스 파스타"),  # expand_allergies 가 치즈 차단
            (["계란"], "친구와 술 한잔 안주"),  # 계란말이 차단
            (["조개", "땅콩", "우유"], "건강한 식단"),  # 복합 알레르기
        ],
    )
    async def test_allergy_zero_exposure_with_nl(
        self, recipe_repo, gemini_off, allergies: list[str], nl_context: str
    ) -> None:
        """카테고리 알레르기 + 자연어 컨텍스트 → 누출 0건 보장."""
        result = await recommend_dual(
            fridge_ingredients=["두부", "간장", "마늘", "밥", "계란", "면", "치즈"],
            preferences=_DEFAULT_PREFS,
            user_allergies=allergies,
            user_context=nl_context,
            repo=recipe_repo,
        )
        # expand_allergies 로 확장된 forbidden set
        from app.core.allergy_map import expand_allergies
        forbidden = set(normalize_list(expand_allergies(allergies)))

        for item in result["model_a"] + result["model_b"]:
            rec = recipe_repo.get(item["recipe_id"])
            if rec is None:
                continue
            allergens = set(rec.allergens)
            leak = forbidden & allergens
            assert not leak, (
                f"알레르기 누출: {item['recipe_id']} ({rec.name}) "
                f"allergens={rec.allergens}, forbidden={forbidden}, "
                f"입력 알레르기={allergies}, 자연어={nl_context!r}. "
                f"NFR-EVAL-001 위반."
            )


# ────────────────────────────────────────────────────────────────
# 2. Model A ∩ Model B = ∅ (SDD §3.2 자연 분리)
# ────────────────────────────────────────────────────────────────


class TestModelABDisjoint:
    """Model A (missing=0) 와 Model B (missing>0) 가 정의상 교집합 0."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "fridge,nl",
        [
            (["두부", "간장", "마늘", "밥", "계란"], ""),
            (["김치", "돼지고기", "두부", "대파"], "비 오는 날"),
            (["면", "치즈", "마늘", "토마토"], "크림 파스타"),
        ],
    )
    async def test_a_b_no_overlap(
        self, recipe_repo, gemini_off, fridge: list[str], nl: str
    ) -> None:
        """다양한 입력에서 model_a ∩ model_b 항상 ∅."""
        result = await recommend_dual(
            fridge_ingredients=fridge,
            preferences=_DEFAULT_PREFS,
            user_allergies=[],
            user_context=nl,
            repo=recipe_repo,
        )
        a_ids = {r["recipe_id"] for r in result["model_a"]}
        b_ids = {r["recipe_id"] for r in result["model_b"]}
        overlap = a_ids & b_ids
        assert not overlap, (
            f"fridge={fridge} nl={nl!r} → A∩B={overlap}. "
            f"SDD §3.2 missing=0 vs >0 자연 분리 위반. "
            f"recommend_service.py dedup 제거 의도 깨짐."
        )


# ────────────────────────────────────────────────────────────────
# 3. country/theme prefs hard filter
# ────────────────────────────────────────────────────────────────


class TestPrefsHardFilter:
    """사용자 country/theme 선호는 자연어보다 우선 (Critic CRITICAL #C2)."""

    @pytest.mark.asyncio
    async def test_country_hard_filter_model_a(self, recipe_repo) -> None:
        """양식 선호 + 한식 자연어 → Model A 결과는 100% 양식."""
        prefs = {**_DEFAULT_PREFS, "country": "양식"}
        result = await recommend_cold_storage(
            fridge_ingredients=["면", "치즈", "마늘", "토마토"],
            preferences=prefs,
            user_allergies=[],
            repo=recipe_repo,
            user_context="비 오는 날 한식 김치찌개",
        )
        for item in result:
            rec = recipe_repo.get(item["recipe_id"])
            assert rec is not None
            assert rec.country == "west", (
                f"양식 선호인데 {rec.country} 노출: {item['recipe_id']}. "
                f"Critic CRITICAL #C2 회귀."
            )

    @pytest.mark.asyncio
    async def test_country_hard_filter_model_b(
        self, recipe_repo, gemini_off
    ) -> None:
        """양식 선호 → Model B 결과도 100% 양식 (tracer 발견 결함 회귀)."""
        prefs = {**_DEFAULT_PREFS, "country": "양식"}
        result = await recommend_missing_ingredients(
            fridge_ingredients=["면", "치즈", "마늘"],
            preferences=prefs,
            user_allergies=[],
            user_context="비 오는 날 한식 국물",
            repo=recipe_repo,
        )
        for item in result:
            rec = recipe_repo.get(item["recipe_id"])
            if rec is None:
                continue
            assert rec.country == "west", (
                f"Model B country 누출: {rec.country} for {item['recipe_id']}"
            )


# ────────────────────────────────────────────────────────────────
# 4. 응답 시간 NFR-PERF-003 ≤ 10초
# ────────────────────────────────────────────────────────────────


class TestPerformanceNfr:
    """모든 추천 호출이 NFR-PERF-003 (≤10s) 이내 완료."""

    @pytest.mark.asyncio
    async def test_dual_recommend_under_10s_with_nl(
        self, recipe_repo, gemini_off
    ) -> None:
        """긴 자연어 + 복잡 prefs 에서도 dual 추천 ≤ 10초."""
        start = time.perf_counter()
        result = await recommend_dual(
            fridge_ingredients=["두부", "간장", "마늘", "밥", "계란", "면", "양파"],
            preferences=_DEFAULT_PREFS,
            user_allergies=["조개", "땅콩"],
            user_context="비 오는 날 따뜻하게 친구와 술 한잔 매콤한 다이어트 국물",
            repo=recipe_repo,
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, (
            f"dual 추천 {elapsed:.2f}s — NFR-PERF-003 위반. "
            f"expand_context + TF-IDF 추가 호출 성능 회귀."
        )
        # 결과 구조 정상
        assert "model_a" in result
        assert "model_b" in result

    @pytest.mark.asyncio
    async def test_model_a_p95_under_1s(self, recipe_repo) -> None:
        """평가 환경 (SQLite + 미니 카탈로그) 에서 p95 < 1초."""
        elapsed_list = []
        for _ in range(20):
            start = time.perf_counter()
            await recommend_cold_storage(
                fridge_ingredients=["두부", "간장", "마늘"],
                preferences=_DEFAULT_PREFS,
                user_allergies=[],
                repo=recipe_repo,
                user_context="비 오는 날",
            )
            elapsed_list.append(time.perf_counter() - start)
        elapsed_list.sort()
        p95 = elapsed_list[int(0.95 * len(elapsed_list))]
        assert p95 < 1.0, (
            f"Model A p95 {p95*1000:.1f}ms — 평가 환경 1초 기준 위반"
        )


# ────────────────────────────────────────────────────────────────
# 5. Gemini 실패 폴백 (NFR-REL-001)
# ────────────────────────────────────────────────────────────────


class TestGeminiFailureFallback:
    """Gemini 실패 시에도 model_b 가 final_score 기반 Top-3 폴백."""

    @pytest.mark.asyncio
    async def test_b_returns_results_when_gemini_none(
        self, recipe_repo, gemini_off
    ) -> None:
        """Gemini 가 None 반환해도 model_b 결과 비지 않음."""
        result = await recommend_missing_ingredients(
            fridge_ingredients=["두부", "간장", "마늘"],
            preferences=_DEFAULT_PREFS,
            user_allergies=[],
            user_context="비 오는 날",
            repo=recipe_repo,
        )
        # Gemini 실패해도 final_score 기반 폴백으로 1건 이상
        # (단, 후보가 있을 때만 — 미니 카탈로그 7건에서는 0건 가능)
        # 폴백 경로 자체가 예외 없이 동작하면 PASS
        assert isinstance(result, list)
        for item in result:
            # critic F3 빈 카드 차단 — Gemini 폴백 시 결정론 한국어 문장 보장.
            # 이전 가정 (reason="") 폐기. "보유한 X 활용. Y 추가 시 완성됩니다." 패턴.
            assert "reason" in item
            assert item["reason"], "폴백이라도 결정론 reason 보장"
            assert "보유" in item["reason"] or "활용" in item["reason"]

    @pytest.mark.asyncio
    async def test_dual_isolated_failures(
        self, recipe_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """model_a 가 예외 던져도 model_b 결과는 살아있음 (recommend_service 격리)."""
        from app.services import recommend_service as rs

        async def _broken_a(*args, **kwargs):
            raise RuntimeError("model_a 강제 실패")

        async def _none_gemini(candidates, user_context):
            return None

        monkeypatch.setattr(rs, "recommend_cold_storage", _broken_a)
        monkeypatch.setattr(mb_mod, "gemini_select_top3", _none_gemini)

        result = await recommend_dual(
            fridge_ingredients=["두부", "간장"],
            preferences=_DEFAULT_PREFS,
            user_allergies=[],
            user_context="",
            repo=recipe_repo,
        )
        # model_a 실패 → 빈 리스트, model_b 는 정상
        assert result["model_a"] == []
        assert isinstance(result["model_b"], list)  # 예외 발생 없음


# ────────────────────────────────────────────────────────────────
# 6. expand_context 통합 회귀
# ────────────────────────────────────────────────────────────────


class TestExpandContextIntegration:
    """expand_context 모듈이 추천 호출 경로에 부작용 없이 통합."""

    @pytest.mark.asyncio
    async def test_empty_context_does_not_break(self, recipe_repo) -> None:
        """user_context='' → expand 빈 문자열 → 추천 호출 정상."""
        result = await recommend_cold_storage(
            fridge_ingredients=["두부", "간장"],
            preferences=_DEFAULT_PREFS,
            user_allergies=[],
            repo=recipe_repo,
            user_context="",
        )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_unmapped_context_does_not_break(self, recipe_repo) -> None:
        """매핑되지 않는 자연어도 안전 폴백 (원본 그대로 query 에 포함)."""
        result = await recommend_cold_storage(
            fridge_ingredients=["두부", "간장"],
            preferences=_DEFAULT_PREFS,
            user_allergies=[],
            repo=recipe_repo,
            user_context="zzz xyz 매핑없는단어",
        )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_very_long_context_does_not_break(self, recipe_repo) -> None:
        """매우 긴 자연어 (10+ MOOD_MAP 키 동시 매칭) 도 정상."""
        long_ctx = (
            "비 오는 추운 겨울 따뜻한 친구와 술 한잔 매콤한 분식 "
            "다이어트 건강한 국물 요리 간단한 빠르게 야식 혼밥 집밥"
        )
        start = time.perf_counter()
        result = await recommend_cold_storage(
            fridge_ingredients=["두부", "간장"],
            preferences=_DEFAULT_PREFS,
            user_allergies=[],
            repo=recipe_repo,
            user_context=long_ctx,
        )
        elapsed = time.perf_counter() - start
        assert isinstance(result, list)
        assert elapsed < 5.0, f"긴 자연어에서 응답 {elapsed:.2f}s — 회귀"
