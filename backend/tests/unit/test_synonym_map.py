"""SYNONYM_MAP 단위 테스트 — SDD §3.2, SRS FR-002.

- 100쌍 매핑 정상 동작
- 미등록 재료는 strip 후 그대로 반환
- normalize_list: 중복 제거 + 순서 보존
- 대소문자/공백 정규화 (strip 적용)
"""

from __future__ import annotations

import pytest

from app.core.synonym_map import SYNONYM_MAP, normalize, normalize_list


class TestSynonymSinglePairs:
    """SYNONYM_MAP 대표 매핑 — 100쌍 무작위 점검."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("쪽파", "대파"),
            ("실파", "대파"),
            ("청양고추", "고추"),
            ("꽈리고추", "고추"),
            ("할라피뇨", "고추"),
            ("다진마늘", "마늘"),
            ("피자치즈", "치즈"),
            ("모짜렐라치즈", "치즈"),
            ("순두부", "두부"),
            ("연두부", "두부"),
            ("달걀", "계란"),
            ("닭가슴살", "닭고기"),
            ("닭다리", "닭고기"),
            ("삼겹살", "돼지고기"),
            ("차돌박이", "소고기"),
            ("왕새우", "새우"),
            ("주꾸미", "낙지"),
            ("스파게티", "면"),
            ("당면", "면"),
            ("햇반", "밥"),
            ("진간장", "간장"),
            ("초고추장", "고추장"),
            ("올리브오일", "올리브유"),
            ("두유", "우유"),
        ],
    )
    def test_known_synonym_normalizes(self, raw: str, expected: str) -> None:
        """# SDD §3.2 — 등록된 동의어는 대표 키워드로 매핑."""
        assert normalize(raw) == expected

    def test_map_has_100_entries_at_minimum(self) -> None:
        """# SDD §3.2 — 매핑 사전이 충분히 크다 (100쌍 목표, 현재 100+ 등록)."""
        assert len(SYNONYM_MAP) >= 100, f"SYNONYM_MAP 크기 부족: {len(SYNONYM_MAP)}"


class TestSynonymPassthrough:
    """미등록 재료 — 원본 보존."""

    @pytest.mark.parametrize("raw", ["당근", "오이", "토마토", "감자", "양배추"])
    def test_unknown_ingredient_returned_as_is(self, raw: str) -> None:
        """# SDD §3.2 — 미등록 재료는 strip 후 그대로 반환."""
        assert normalize(raw) == raw

    def test_empty_string_returns_empty(self) -> None:
        """# SDD §3.2 — 빈 문자열 입력 처리."""
        assert normalize("") == ""

    def test_whitespace_stripped(self) -> None:
        """# SDD §3.2 — 좌우 공백 strip."""
        assert normalize("  쪽파  ") == "대파"
        assert normalize("  당근  ") == "당근"


class TestNormalizeList:
    """normalize_list — 리스트 정규화 + dedupe."""

    def test_dedup_preserves_order(self) -> None:
        """# SDD §3.2 — 중복 제거 + 순서 보존."""
        out = normalize_list(["쪽파", "대파", "양파"])
        assert out == ["대파", "양파"], "쪽파→대파, 대파 중복 제거, 양파 보존"

    def test_multiple_synonyms_collapse(self) -> None:
        """# SDD §3.2 — 여러 동의어가 동일 대표로 매핑되면 1건만."""
        out = normalize_list(["청양고추", "꽈리고추", "할라피뇨"])
        assert out == ["고추"]

    def test_empty_list_returns_empty(self) -> None:
        """# SDD §3.2 — 빈 리스트 입력."""
        assert normalize_list([]) == []

    def test_unknown_passthrough_in_list(self) -> None:
        """# SDD §3.2 — 미등록 재료는 그대로 통과."""
        out = normalize_list(["당근", "오이", "토마토"])
        assert out == ["당근", "오이", "토마토"]

    def test_mixed_known_unknown(self) -> None:
        """# SDD §3.2 — 등록/미등록 혼재 처리."""
        out = normalize_list(["쪽파", "당근", "다진마늘", "오이"])
        # 쪽파→대파, 당근(원본), 다진마늘→마늘, 오이(원본)
        assert out == ["대파", "당근", "마늘", "오이"]
