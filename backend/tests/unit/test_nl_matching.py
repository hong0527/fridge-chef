"""자연어 매칭 (expand_context) 단위 테스트 — Issue #72 후속.

`backend/app/services/context_expander.py` 의 `expand_context()` 가
MOOD_MAP(60+ 키) 기반 자연어→1667 운영 vocab 키워드 매핑을 정확히
수행하는지 광역 검증한다.

목적:
  1. MOOD_MAP 60+ 카테고리 대표 키마다 1개 이상 케이스로 회귀 보장
  2. 빈 입력·매핑 없는 입력·부분 매칭 등 엣지 케이스 안전 검증
  3. 학부 평가관 시연 자연어 ("비 오는 날" 등) 동작 보증

기존 `test_context_expander.py` 가 9개 케이스만 다루던 한계 보강.

참조:
  - Salton & McGill 1983 §6 Query Expansion
  - Manning et al. 2008 IIR §9 Relevance Feedback
"""

from __future__ import annotations

import pytest

from app.services.context_expander import MOOD_MAP, expand_context


# ────────────────────────────────────────────────────────────────
# 1. 빈 입력·매핑 없는 입력 — 안전 폴백
# ────────────────────────────────────────────────────────────────


class TestSafeFallback:
    """공백·빈 문자열·매핑 없는 입력은 부수효과 없이 통과해야 한다."""

    def test_empty_string_returns_empty(self) -> None:
        assert expand_context("") == ""

    def test_whitespace_only_returns_as_is(self) -> None:
        assert expand_context("   ") == "   "
        assert expand_context("\t\n") == "\t\n"

    def test_no_mapping_returns_original_unchanged(self) -> None:
        """MOOD_MAP 키 어느 하나도 부분 일치하지 않으면 원본 그대로."""
        original = "전혀 매칭되지 않는 zzz xyz qwerty"
        assert expand_context(original) == original

    def test_none_unsafe_input_handled_via_empty(self) -> None:
        """방어적 — 빈 문자열 처리는 함수가 try/except 없이도 안전."""
        # falsy 안전 폴백 검증 (None 은 호출자 책임이지만 빈 ""는 보장)
        assert expand_context("") == ""


# ────────────────────────────────────────────────────────────────
# 2. 카테고리별 대표 1개 — 핵심 매핑 회귀 (60+ 키 중 18개 샘플)
# ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "user_ctx,expected_tokens",
    [
        # 날씨·온도 (kr/soup 카테고리)
        ("비 오는 날", ["김치", "두부", "참치김치찌개"]),
        ("추운 겨울 아침", ["김치", "쇠고기", "미역국"]),
        ("따뜻한 한 끼", ["김치", "두부", "정통일본식우동"]),
        ("더운 여름날", ["오이", "양상추", "토마토"]),
        # 상황·동반
        ("친구와 술 한잔", ["계란말이", "감자전", "두부"]),
        ("혼밥 메뉴 추천", ["라면", "콩나물비빔밥", "오므라이스"]),
        ("야식 먹고 싶다", ["라면", "치즈떡볶이", "간장떡볶이"]),
        # 시간·난이도
        ("간단한 저녁", ["콩나물비빔밥", "라면", "회덮밥"]),
        ("빠르게 만들 수 있는", ["라면", "계란말이", "오므라이스"]),
        ("고급 정성 요리", ["잡채", "스테이크", "찹스테이크"]),
        # 맛
        ("매콤한 거", ["고추장", "치즈떡볶이"]),
        ("달콤한 디저트", ["고구마", "설탕"]),
        ("담백한 한식", ["미역국", "두부", "콩나물"]),
        # 건강·식단
        ("다이어트 식단", ["샐러드", "케이준치킨샐러드", "흑미"]),
        ("저칼로리 반찬", ["샐러드", "콩나물", "오이"]),
        # 음식 종류
        ("토마토 파스타", ["토마토파스타", "치즈"]),
        ("크림 베이스 진한 파스타", ["까르보나라", "버터"]),
        ("우동 한 그릇", ["우동", "정통일본식우동", "철판우동"]),
    ],
)
def test_category_representative_mapping(
    user_ctx: str, expected_tokens: list[str]
) -> None:
    """각 MOOD_MAP 카테고리 대표 입력이 1667 vocab 토큰으로 정확 확장."""
    result = expand_context(user_ctx)
    # 원본 보존
    assert user_ctx in result, f"원본 누락: {result}"
    # 도메인 키워드 확장
    for kw in expected_tokens:
        assert kw in result, f"'{user_ctx}' → '{kw}' 누락. 결과: {result}"


# ────────────────────────────────────────────────────────────────
# 3. 부분 매칭 — 자연 문장 안의 키 포함
# ────────────────────────────────────────────────────────────────


class TestPartialMatching:
    """MOOD_MAP 키가 자연 문장 어딘가에 부분 문자열로 등장하면 매칭."""

    def test_partial_inside_longer_sentence(self) -> None:
        """'비 오는 따뜻한 날 친구와' → 비 오는 + 따뜻한 + 친구와 3개 키 동시 매칭."""
        result = expand_context("비 오는 따뜻한 날 친구와 만남")
        # 비 오는 → 김치/두부/된장
        assert "김치" in result
        # 따뜻한 → 미역국/쇠고기/우동
        assert "미역국" in result
        # 친구와 → 계란말이/감자전
        assert "계란말이" in result

    def test_key_at_string_start(self) -> None:
        """키가 문자열 시작에 등장."""
        result = expand_context("매운 음식 좋아요")
        assert "고추장" in result

    def test_key_at_string_end(self) -> None:
        """키가 문자열 끝에 등장."""
        result = expand_context("오늘은 분식")
        assert "치즈떡볶이" in result or "간장떡볶이" in result

    def test_korean_postposition_absorbed(self) -> None:
        """한국어 조사 흡수 — '겨울에', '겨울이' 모두 '겨울' 매칭."""
        a = expand_context("겨울에 먹는 음식")
        b = expand_context("겨울이 다가오면")
        # 두 입력 모두 '미역국' 또는 '쇠고기' 확장 (겨울 → 김치·두부·된장·미역국)
        assert "미역국" in a or "쇠고기" in a
        assert "미역국" in b or "쇠고기" in b


# ────────────────────────────────────────────────────────────────
# 4. 자료구조 무결성 — MOOD_MAP 자체 검증
# ────────────────────────────────────────────────────────────────


class TestMoodMapIntegrity:
    """MOOD_MAP 자료구조 정합성 — 학부 발표 자료 신뢰성 보장."""

    def test_minimum_60_keys(self) -> None:
        """학부 발표 자료 ('MOOD_MAP 60+ 키') 충족."""
        assert len(MOOD_MAP) >= 60, (
            f"MOOD_MAP 키 {len(MOOD_MAP)}개 — 발표 자료 '60+'와 불일치"
        )

    def test_all_keys_are_korean_strings(self) -> None:
        """모든 키는 비어있지 않은 한국어 문자열."""
        for key in MOOD_MAP.keys():
            assert isinstance(key, str)
            assert len(key.strip()) > 0
            # 한글 1자 이상 포함 (영문 키 방지)
            assert any("가" <= c <= "힯" for c in key), (
                f"한국어 키 아님: '{key}'"
            )

    def test_all_values_are_non_empty_lists(self) -> None:
        """모든 값은 1개 이상 키워드를 가진 리스트."""
        for key, kws in MOOD_MAP.items():
            assert isinstance(kws, list), f"{key} 값이 list 아님"
            assert len(kws) > 0, f"{key} 키워드 비어있음"
            for kw in kws:
                assert isinstance(kw, str)
                assert len(kw.strip()) > 0


# ────────────────────────────────────────────────────────────────
# 5. 중복 제거 + 순서 안정성
# ────────────────────────────────────────────────────────────────


class TestExpansionInvariants:
    """확장 결과의 불변식 — 학부 평가에서 결정론·재현성 보장."""

    def test_no_duplicate_keywords_across_multi_key_match(self) -> None:
        """여러 키가 같은 키워드 매핑해도 중복 추가 없음."""
        # '따뜻한', '비 오는', '추운', '겨울' 4개 키 — 모두 '김치' 공유
        result = expand_context("따뜻한 비 오는 추운 겨울 메뉴")
        # 원본 이후 확장된 부분만 추출
        prefix_end = result.find("메뉴") + len("메뉴 ")
        expanded_tokens = result[prefix_end:].split()
        # 확장 토큰은 모두 unique
        assert len(set(expanded_tokens)) == len(expanded_tokens), (
            f"중복 토큰: {expanded_tokens}"
        )
        # 핵심 어휘 1회만 등장
        assert expanded_tokens.count("김치") == 1

    def test_original_always_prefix(self) -> None:
        """결과는 항상 원본 + 공백 + 확장 토큰 (UI 표시 안전)."""
        original = "친구와 술 한잔"
        result = expand_context(original)
        assert result.startswith(original), (
            f"원본 prefix 깨짐: '{result}' vs '{original}'"
        )

    def test_expansion_actually_extends(self) -> None:
        """매핑되는 입력은 결과 길이가 원본보다 길어져야 함."""
        result = expand_context("비 오는 날")
        assert len(result) > len("비 오는 날")

    def test_deterministic_repeat_call(self) -> None:
        """동일 입력 → 동일 출력 (결정론 — 학부 발표 재현성)."""
        ctx = "추운 겨울 매운 국물"
        r1 = expand_context(ctx)
        r2 = expand_context(ctx)
        assert r1 == r2


# ────────────────────────────────────────────────────────────────
# 6. 시연 핵심 시나리오 — 발표 라이브 입력 보증
# ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "demo_input,must_contain",
    [
        # 시연 1: 비 오는 날 (TF-IDF 핵심 효과)
        ("비 오는 날 따뜻하게 먹을 국물 요리", ["김치", "두부", "참치김치찌개"]),
        # 시연 2: 다이어트 (저칼로리 매칭)
        ("건강한 식단 다이어트", ["샐러드", "콩나물"]),
        # 시연 3: 술안주 (분식·전류)
        ("친구와 술 한잔 안주", ["계란말이", "감자전"]),
        # 시연 4: 겨울 매콤 (복합 의도)
        ("추운 겨울 매콤한 국물", ["김치", "고추장"]),
        # 시연 5: 집밥 향수 (감성)
        ("엄마가 해주시던 집밥", ["쇠고기", "미역국"]),
    ],
)
def test_demo_scenario_robust_expansion(
    demo_input: str, must_contain: list[str]
) -> None:
    """학부 평가관 시연 라이브 입력 — 모든 핵심 키워드 확장 회귀 보호."""
    result = expand_context(demo_input)
    for kw in must_contain:
        assert kw in result, (
            f"시연 입력 '{demo_input}' → 확장에 '{kw}' 누락. "
            f"학부 발표 라이브 시연 깨질 위험. 결과: {result}"
        )
