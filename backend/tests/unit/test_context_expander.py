"""ContextExpander 단위 테스트 — 자연어→코퍼스 키워드 매핑 검증.

Issue #72 Critic 진단 보강. user_context OOV 문제 해소를 위한 도메인 키워드
확장이 의도대로 작동하는지 회귀 테스트.
"""

from __future__ import annotations

import pytest

from app.services.context_expander import MOOD_MAP, expand_context


class TestExpandContext:
    def test_empty_returns_as_is(self) -> None:
        assert expand_context("") == ""
        assert expand_context("   ") == "   "

    def test_no_match_returns_original(self) -> None:
        # 매핑에 없는 문장은 그대로 — 안전 폴백 (overfitting 방지)
        original = "전혀 매칭되지 않는 단어들 zzz xyz"
        assert expand_context(original) == original

    def test_rainy_day_expands_to_soup_keywords(self) -> None:
        """'비 오는 날' → '김치찌개·된장찌개·순두부찌개' 확장 — TF-IDF vocab 통토큰."""
        result = expand_context("비 오는 날 따뜻하게 먹을 국물 요리")
        # 원본 보존
        assert "비 오는 날" in result
        # vocab 통토큰 키워드 추가 — 시드 35 vocab에 실제 존재하는 토큰만
        for kw in ["김치찌개", "된장찌개", "순두부찌개"]:
            assert kw in result

    def test_drink_with_friend_expands_to_anju(self) -> None:
        """'친구와 술 한잔' → '계란말이·감자전·두부조림' 확장."""
        result = expand_context("친구와 술 한잔 안주")
        assert "친구와" in result  # 원본 토큰 보존
        # 부침·말이 통토큰
        assert "계란말이" in result
        assert "감자전" in result

    def test_diet_expands_to_salad_vegetable(self) -> None:
        """'건강한 다이어트' → '샐러드·야채볶음' 확장."""
        result = expand_context("건강한 식단 다이어트")
        assert "샐러드" in result
        assert "야채볶음" in result

    def test_winter_spicy_expands_to_stew(self) -> None:
        """'추운 겨울 매운' → '김치찌개·고추장·떡볶이' 확장."""
        result = expand_context("추운 겨울 매운 국물")
        assert "김치찌개" in result
        assert "고추장" in result  # '매운' → '고추장' 매핑

    def test_no_duplicate_keywords(self) -> None:
        """여러 키가 같은 키워드 매핑 시에도 중복 없이 한 번만 추가."""
        result = expand_context("따뜻한 비 오는 날 추운 겨울")
        # '김치찌개' 는 여러 매핑 키에서 등장하지만 출력에는 1번만
        assert result.count("김치찌개") == 1
        assert result.count("된장찌개") == 1

    def test_multiple_distinct_categories(self) -> None:
        """여러 카테고리(분식+매콤) 동시 매칭."""
        result = expand_context("분식집 매콤한 거")
        assert "떡볶이" in result  # 분식
        assert "고추장" in result  # 매콤

    def test_original_text_always_prefixed(self) -> None:
        """확장 결과는 항상 원본 + 추가 키워드 형태."""
        original = "비 오는 날"
        result = expand_context(original)
        assert result.startswith(original)
        assert len(result) > len(original)

    def test_mood_map_keywords_are_strings(self) -> None:
        """MOOD_MAP 자료구조 무결성 — 모든 키워드는 str."""
        for key, kws in MOOD_MAP.items():
            assert isinstance(key, str)
            assert isinstance(kws, list)
            assert all(isinstance(k, str) for k in kws)
            assert len(kws) > 0


@pytest.mark.parametrize(
    "user_ctx,must_contain",
    [
        ("간단한 덮밥", ["오므라이스", "규동"]),
        ("토마토 파스타", ["토마토파스타"]),
        ("크림 베이스 진한 파스타", ["까르보나라"]),
        ("두부 위주 매운 중식", ["마파두부", "고추장"]),
        ("혼밥 빠르게", ["라면", "비빔밥"]),
        ("분식집 매콤한 거", ["떡볶이"]),
    ],
)
def test_scenario_keyword_expansion(user_ctx: str, must_contain: list[str]) -> None:
    """eval_tfidf_scenarios.json 시나리오별 user_context 가 의도된 도메인 키워드로 확장."""
    result = expand_context(user_ctx)
    for kw in must_contain:
        assert kw in result, f"'{user_ctx}' 확장 결과에 '{kw}' 누락: {result}"
