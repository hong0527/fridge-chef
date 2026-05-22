"""synonym_map.py 엣지 케이스·잘못된 매핑 탐지.

확인 사항:
1. 자기 매핑 (예: '참기름' → '참기름') 의미 없음 (LOW)
2. '두유' → '우유' 는 알레르기 충돌 (대두 vs 우유) — 위험한 정규화 (HIGH, xfail)
3. '주꾸미' → '낙지' 매칭이지만 시드에 '낙지' 없음 (HIGH)
4. '유부' → '두부'는 다른 식재료 (MEDIUM, xfail)
5. 빈 문자열·None 안전 처리
6. 중복 제거 + 순서 보존
"""

from __future__ import annotations

import pytest

from app.core.synonym_map import SYNONYM_MAP, normalize, normalize_list

# ────────────────────────────────────────────────────────────────
# 결함 #1 (LOW): 자기 매핑 무의미
# ────────────────────────────────────────────────────────────────


def test_self_mapping_is_redundant() -> None:
    """'참기름' → '참기름', '들기름' → '들기름' 같은 자기 매핑은 dict에 없어도 동일하게 동작."""
    self_maps = [k for k, v in SYNONYM_MAP.items() if k == v]
    assert len(self_maps) > 0, "자기 매핑 케이스가 존재함"
    # 자기 매핑은 SYNONYM_MAP에서 제거 가능 — normalize()는 fallback으로 strip 후 원본 반환
    for key in self_maps:
        # SYNONYM_MAP에 있든 없든 결과는 동일해야 함
        assert normalize(key) == key


# ────────────────────────────────────────────────────────────────
# 결함 #2 (HIGH, xfail): 두유 → 우유 매핑이 알레르기 충돌
# ────────────────────────────────────────────────────────────────


@pytest.mark.xfail(
    reason="HIGH 위험: '두유'는 대두 알레르기 카테고리, '우유'는 우유 알레르기 카테고리. "
    "정규화로 같은 키워드가 되면 알레르기 필터링이 잘못 동작할 수 있음.",
    strict=False,
)
def test_soy_milk_should_not_map_to_milk() -> None:
    """'두유'는 대두 카테고리이므로 '우유'로 정규화되면 안 됨."""
    assert SYNONYM_MAP.get("두유") != "우유", (
        "'두유' → '우유' 매핑은 알레르기 충돌. "
        "대두 알레르기 사용자에게 '두유' 든 레시피가 우유로 분류돼 차단 실패 가능."
    )


# ────────────────────────────────────────────────────────────────
# 결함 #3 (HIGH): '주꾸미' → '낙지'이지만 시드에 '낙지' 없음
# ────────────────────────────────────────────────────────────────


def test_jjukkumi_maps_to_nakji_check() -> None:
    """'주꾸미' → '낙지' 매핑 존재. 그러나 시드 레시피에 '낙지' 사용처 확인."""
    from app.models.recipe_repository import SEED_RECIPES

    assert normalize("주꾸미") == "낙지"
    all_ings = {ing for r in SEED_RECIPES for ing in r.whole_ingredients}
    # 시드에 '낙지'가 없으면 정규화 의미 없음
    if "낙지" not in all_ings:
        pytest.xfail(
            "'주꾸미' → '낙지' 매핑은 있으나 시드에 '낙지' 사용 레시피 없음 → 매칭 0%"
        )


# ────────────────────────────────────────────────────────────────
# 결함 #4 (MEDIUM, xfail): '유부' → '두부' 매핑 의심
# ────────────────────────────────────────────────────────────────


@pytest.mark.xfail(
    reason="MEDIUM: '유부'(두부튀김)와 '두부'(생/연/순두부)는 식감·요리법이 달라 "
    "동일 키워드로 정규화는 부적절.",
    strict=False,
)
def test_yubu_should_not_map_to_dubu() -> None:
    """'유부'는 '두부'와 다른 식재료."""
    assert SYNONYM_MAP.get("유부") != "두부", (
        "'유부' → '두부' 매핑 재검토 필요"
    )


# ────────────────────────────────────────────────────────────────
# 결함 #5: 빈 입력 안전 처리
# ────────────────────────────────────────────────────────────────


def test_normalize_empty_string() -> None:
    """빈 문자열 입력 시 빈 문자열 반환 (예외 발생 금지)."""
    assert normalize("") == ""


def test_normalize_whitespace_only() -> None:
    """공백만 있는 입력은 strip 후 빈 문자열."""
    # normalize("  ") → strip 후 "" → SYNONYM_MAP.get("", "") → ""
    assert normalize("  ") == ""


def test_normalize_list_filters_empty() -> None:
    """normalize_list는 빈 결과를 결과 리스트에서 제외."""
    out = normalize_list(["계란", "", "  ", "두부"])
    assert "" not in out
    assert "  " not in out
    assert "계란" in out and "두부" in out


# ────────────────────────────────────────────────────────────────
# 결함 #6: 중복 제거 + 순서 보존
# ────────────────────────────────────────────────────────────────


def test_normalize_list_dedup_preserves_order() -> None:
    """동의어가 같은 정규형으로 매핑되면 중복 제거 + 첫 등장 순서 보존."""
    out = normalize_list(["쪽파", "대파", "양파", "실파"])
    # 쪽파→대파, 실파→대파 모두 '대파'로 정규화 → 중복 제거
    assert out == ["대파", "양파"], f"순서·중복제거 실패: {out}"


def test_normalize_list_handles_categories_with_synonyms() -> None:
    """알레르기 카테고리("난류")는 SYNONYM_MAP에 없음 → 그대로 반환."""
    out = normalize_list(["난류", "달걀", "메추리알"])
    # 달걀, 메추리알 → 계란 (중복 제거)
    # 난류는 그대로
    assert "난류" in out
    assert "계란" in out
    assert "달걀" not in out  # 정규화됨
    assert "메추리알" not in out  # 정규화됨


# ────────────────────────────────────────────────────────────────
# 결함 #7: 의도된 누락 확인 (보고용)
# ────────────────────────────────────────────────────────────────


def test_missing_common_synonyms_inventory() -> None:
    """자주 쓰이는데 SYNONYM_MAP에 없는 케이스 리포트 (필요 시 추가용)."""
    expected_but_missing = {
        "스리라차": "고추",  # 인기 핫소스
        "참외": "참외",  # 그대로 — 매핑 불필요
        "방울토마토": "토마토",
        "대추": "대추",
        "케일": "케일",
    }
    # 정보 수집용 — 실패 시 SYNONYM_MAP 확장 후보 알림
    missing = [k for k, v in expected_but_missing.items()
               if v != k and SYNONYM_MAP.get(k) != v]
    if missing:
        # 정보성 — 실패가 아님
        pytest.skip(f"확장 후보 (정보성): {missing}")
