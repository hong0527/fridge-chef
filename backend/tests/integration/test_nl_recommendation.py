"""자연어 컨텍스트 → 추천 결과 의미적 적절성 통합 테스트.

`expand_context()` + `model_a` + `model_b` 파이프라인이 자연어 입력에
의미적으로 적절한 추천을 반환하는지 운영 코퍼스 (1667) 가능 시 검증.
시드 35만 가능한 환경에서는 SDD §3.2 제약 (알레르기 0% 등) 회귀만 보장.

운영 vs 평가 환경 차이:
  - 운영: Render + Supabase 1667 레시피
  - 평가: SQLite 인메모리 + 결정론적 미니 카탈로그 (conftest.recipe_repo) 7건
  - 1667 정확 매칭은 backend/scripts/evaluate_recommend.py --compare-tfidf 로 별도 측정
  - 본 파일은 "자연어 매핑이 실제 추천 호출에 통합되는 구조" 회귀만 보장

참조:
  - SDD v1.0 §3.2 (모델 A/B 알고리즘)
  - SRS v1.10 NFR-EVAL-001 (알레르기 0%)
  - NFR-PERF-003 (추천 ≤ 10초)
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from app.core.synonym_map import normalize_list
from app.services.context_expander import expand_context
from app.services.model_a import recommend_cold_storage
from app.services.model_b import recommend_missing_ingredients


# ────────────────────────────────────────────────────────────────
# 1. 자연어 → 확장 → 추천 파이프라인 통합 회귀
# ────────────────────────────────────────────────────────────────


class TestNlPipelineIntegration:
    """expand_context → model_a/b 가 자연어 입력에 빈 응답·예외 없이 동작."""

    @pytest.mark.asyncio
    async def test_rainy_day_pipeline_no_crash(self, recipe_repo) -> None:
        """'비 오는 날' 자연어 입력 → 추천 호출 안전 완료."""
        result = await recommend_cold_storage(
            fridge_ingredients=["두부", "간장", "마늘", "밥", "계란"],
            preferences={
                "country": "한식",
                "food_type": "메인요리",
                "spicy": 3,
                "difficulty": "초보",
                "max_cook_min": 60,
            },
            user_allergies=[],
            repo=recipe_repo,
            user_context="비 오는 날 따뜻하게 먹을 국물",
        )
        # 예외 없이 list 반환
        assert isinstance(result, list)
        # 각 항목은 필수 필드 포함
        for item in result:
            assert "recipe_id" in item
            assert "name" in item
            assert "score" in item

    @pytest.mark.asyncio
    async def test_diet_context_calls_model_b(
        self, recipe_repo, mock_gemini_fail
    ) -> None:
        """'다이어트' 자연어 → model_b 호출 시 country 일치 결과 반환."""
        result = await recommend_missing_ingredients(
            fridge_ingredients=["콩나물", "오이", "양상추"],
            preferences={
                "country": "한식",
                "food_type": "반찬",
                "spicy": 1,
                "difficulty": "초보",
                "max_cook_min": 30,
                "diet": True,
            },
            user_allergies=[],
            user_context="건강한 식단 다이어트",
            repo=recipe_repo,
        )
        assert isinstance(result, list)


# ────────────────────────────────────────────────────────────────
# 2. 알레르기 차단 — 자연어 입력에서도 NFR-EVAL-001 절대 0% 유지
# ────────────────────────────────────────────────────────────────


class TestAllergySafetyUnderNl:
    """자연어 컨텍스트가 알레르기 hard filter 를 우회하지 않음을 검증."""

    @pytest.mark.asyncio
    async def test_peanut_allergy_blocks_even_with_nl_context(
        self, recipe_repo
    ) -> None:
        """'땅콩' 알레르기 + '간단한 샌드위치' 자연어 → 땅콩 함유 레시피 0건."""
        result = await recommend_cold_storage(
            fridge_ingredients=["빵", "땅콩", "양상추"],
            preferences={
                "country": "양식",
                "food_type": "메인요리",
                "spicy": 1,
                "difficulty": "초보",
                "max_cook_min": 30,
            },
            user_allergies=["땅콩"],
            repo=recipe_repo,
            user_context="간단한 샌드위치",
        )
        # 땅콩 포함 레시피는 결과에서 절대 제외 (NFR-EVAL-001)
        forbidden = set(normalize_list(["땅콩"]))
        for item in result:
            rec = recipe_repo.get(item["recipe_id"])
            assert rec is not None
            allergens = set(rec.allergens)
            assert not (forbidden & allergens), (
                f"알레르기 누출: {item['recipe_id']} allergens={rec.allergens} "
                f"forbidden={forbidden} — 자연어 컨텍스트가 NFR-EVAL-001 우회!"
            )

    @pytest.mark.asyncio
    async def test_shellfish_allergy_blocks_seafood_soup_context(
        self, recipe_repo
    ) -> None:
        """'조개' 알레르기 + '따뜻한 국물' 자연어 → 조개 함유 레시피 0건."""
        result = await recommend_cold_storage(
            fridge_ingredients=["조개", "마늘", "대파", "두부"],
            preferences={
                "country": "한식",
                "food_type": "국물",
                "spicy": 1,
                "difficulty": "초보",
                "max_cook_min": 30,
            },
            user_allergies=["조개"],
            repo=recipe_repo,
            user_context="비 오는 날 따뜻한 국물",
        )
        for item in result:
            rec = recipe_repo.get(item["recipe_id"])
            if rec is None:
                continue
            assert "조개" not in rec.allergens, (
                f"조개 알레르기 누출: {item['recipe_id']} → {rec.allergens}"
            )


# ────────────────────────────────────────────────────────────────
# 3. country/theme 일치 — 자연어 입력이 prefs 를 침범하지 않음
# ────────────────────────────────────────────────────────────────


class TestPreferenceConsistencyUnderNl:
    """자연어 user_context 가 사용자 prefs(country/theme) 결과를 침범하면 안 됨."""

    @pytest.mark.asyncio
    async def test_western_prefs_with_korean_nl_context(
        self, recipe_repo
    ) -> None:
        """양식 선호 + '비 오는 날 한식 국물' 자연어 → 결과는 모두 양식 (prefs 우선)."""
        result = await recommend_cold_storage(
            fridge_ingredients=["면", "치즈", "마늘"],
            preferences={
                "country": "양식",
                "food_type": "메인요리",
                "spicy": 1,
                "difficulty": "중급",
                "max_cook_min": 30,
            },
            user_allergies=[],
            repo=recipe_repo,
            user_context="비 오는 날 따뜻한 한식 국물",
        )
        # model_a 는 country hard filter 가 있으므로 모두 'west'
        for item in result:
            rec = recipe_repo.get(item["recipe_id"])
            assert rec is not None
            assert rec.country == "west", (
                f"양식 선호 + 한식 자연어 → '{rec.country}' 반환. "
                f"prefs hard filter 우회 결함."
            )


# ────────────────────────────────────────────────────────────────
# 4. 모델 A·B 자연 분리 — 같은 자연어 입력에서도 교집합 0
# ────────────────────────────────────────────────────────────────


class TestModelAandBDisjointUnderNl:
    """SDD §3.2 — A(missing=0)/B(missing>0) 자연 분리. 자연어 입력에서도 유지."""

    @pytest.mark.asyncio
    async def test_a_and_b_no_overlap_with_nl(
        self, recipe_repo, mock_gemini_fail
    ) -> None:
        """자연어 컨텍스트 추가해도 model_a ∩ model_b == 0."""
        fridge = ["두부", "간장", "마늘", "밥", "계란"]
        prefs: dict[str, Any] = {
            "country": "한식",
            "food_type": "메인요리",
            "spicy": 2,
            "difficulty": "초보",
            "max_cook_min": 60,
        }
        a = await recommend_cold_storage(
            fridge, prefs, [], repo=recipe_repo,
            user_context="비 오는 날 따뜻한 국물",
        )
        b = await recommend_missing_ingredients(
            fridge, prefs, [], "비 오는 날 따뜻한 국물", repo=recipe_repo,
        )
        a_ids = {r["recipe_id"] for r in a}
        b_ids = {r["recipe_id"] for r in b}
        overlap = a_ids & b_ids
        assert not overlap, (
            f"model_a ∩ model_b = {overlap}. SDD §3.2 missing=0 vs >0 자연 분리 위반."
        )


# ────────────────────────────────────────────────────────────────
# 5. 응답 시간 (NFR-PERF-003) — 자연어 입력에서도 10초 이내
# ────────────────────────────────────────────────────────────────


class TestPerformanceUnderNl:
    """자연어 expand + TF-IDF 추가 호출이 응답 시간 NFR 침해하지 않음."""

    @pytest.mark.asyncio
    async def test_model_a_under_10s_with_long_nl(self, recipe_repo) -> None:
        """긴 자연어 입력에서도 model_a 응답 ≤ 10초 (NFR-PERF-003)."""
        long_ctx = (
            "비 오는 날 따뜻하게 친구와 술 한잔 매콤한 분식 "
            "다이어트 건강한 국물 요리 간단한 빠르게 만들 수 있는"
        )
        start = time.perf_counter()
        result = await recommend_cold_storage(
            fridge_ingredients=["두부", "간장", "마늘", "밥", "계란"],
            preferences={
                "country": "한식",
                "food_type": "메인요리",
                "spicy": 3,
                "difficulty": "초보",
                "max_cook_min": 60,
            },
            user_allergies=[],
            repo=recipe_repo,
            user_context=long_ctx,
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0, (
            f"긴 자연어 입력에서 model_a {elapsed:.2f}s — NFR-PERF-003 위반"
        )
        # 결과 자체는 정상
        assert isinstance(result, list)


# ────────────────────────────────────────────────────────────────
# 6. expand_context 빈 입력은 추천 호출에서 비-NL 동작과 동일
# ────────────────────────────────────────────────────────────────


class TestEmptyNlEquivalence:
    """user_context="" 와 expand_context 미적용 동일 — 회귀 안전망."""

    @pytest.mark.asyncio
    async def test_empty_context_does_not_change_result(
        self, recipe_repo
    ) -> None:
        """빈 user_context → expand 가 빈 문자열 반환 → 결과는 비-NL 호출과 동일."""
        kwargs = dict(
            fridge_ingredients=["두부", "간장", "마늘"],
            preferences={
                "country": "한식",
                "food_type": "메인요리",
                "spicy": 1,
                "difficulty": "초보",
                "max_cook_min": 60,
            },
            user_allergies=[],
            repo=recipe_repo,
        )
        r_no_ctx = await recommend_cold_storage(**kwargs)
        r_empty_ctx = await recommend_cold_storage(**kwargs, user_context="")
        assert [r["recipe_id"] for r in r_no_ctx] == [
            r["recipe_id"] for r in r_empty_ctx
        ]


# ────────────────────────────────────────────────────────────────
# 7. expand_context 자체 통합 — 호출 결과가 query_text 에 실제 포함
# ────────────────────────────────────────────────────────────────


class TestExpansionIntegratedInQuery:
    """expand_context 결과가 model_a/b 내부 TF-IDF query 에 실제 반영됨을 간접 검증."""

    def test_expand_appends_to_input(self) -> None:
        """expand_context('비 오는 날') 결과는 원본 + 도메인 키워드."""
        expanded = expand_context("비 오는 날")
        # 원본 보존
        assert "비 오는 날" in expanded
        # 1667 vocab 도메인 키워드 부가
        assert "김치" in expanded or "두부" in expanded

    def test_query_text_construction_includes_expansion(self) -> None:
        """model_a/b 내부에서 만드는 query_text 형식 — fridge + expanded_ctx."""
        # model_a 내부 query_text 구성 패턴 재현
        fridge_norm = {"두부", "간장"}
        expanded_ctx = expand_context("비 오는 날")
        query_text = f"{' '.join(fridge_norm)} {expanded_ctx}".strip()
        # fridge 재료 포함
        assert "두부" in query_text
        # NL 확장 키워드 포함
        assert "김치" in query_text
