"""이름 기반 allergen 추출 테스트 — NA-001~004 (b4da656 회귀 방지).

b4da656에서 추가된 extract_allergens([name]) 보조 태깅 경로가
올바르게 동작하는지 확인한다.

커버리지:
  NA-001  "치즈토마토"                        → 우유 알레르기 태깅
  NA-002  "땅콩쿠키"                          → 땅콩 알레르기 태깅
  NA-003  "야채볶음"                          → false positive 없음 ([])
  NA-004  "계란볶음밥" (이름+재료 모두 계란)   → 중복 없이 ["계란"] 1개
"""

from __future__ import annotations

from scripts.import_real_recipes import extract_allergens


class TestNameAllergenExtraction:
    """NA-001~004: 이름 기반 allergen 추출."""

    def test_NA001_cheese_name_tags_milk_allergen(self) -> None:
        """NA-001 — "치즈토마토": 우유 알레르기 태깅.

        재료 목록에 치즈가 없어도 메뉴 이름에서 치즈 → 우유 알레르기를 감지해야 한다.
        """
        result = extract_allergens(["치즈토마토"])
        assert "우유" in result

    def test_NA002_peanut_name_tags_peanut_allergen(self) -> None:
        """NA-002 — "땅콩쿠키": 땅콩 알레르기 태깅.

        이름에 땅콩이 포함된 경우 땅콩 알레르기가 감지되어야 한다.
        """
        result = extract_allergens(["땅콩쿠키"])
        assert "땅콩" in result

    def test_NA003_vegetable_stir_fry_has_no_allergen(self) -> None:
        """NA-003 — "야채볶음": false positive 없음.

        알레르기 성분이 없는 이름에서는 어떤 알레르기도 태깅되지 않아야 한다.
        "야", "채", "볶", "음" 같은 글자가 패턴에 잘못 매칭되면 안 된다.
        """
        result = extract_allergens(["야채볶음"])
        assert result == []

    def test_NA004_duplicate_allergen_from_name_and_ingredient_is_deduplicated(self) -> None:
        """NA-004 — 이름+재료 양쪽에 계란: 중복 없이 ["계란"] 1개.

        row_to_recipe 조합 로직(sorted(set(name_allergens + ing_allergens)))과
        동일한 방식으로 검증한다.
        """
        name_allergens = extract_allergens(["계란볶음밥"])
        ing_allergens = extract_allergens(["계란"])
        combined = sorted(set(name_allergens + ing_allergens))
        assert combined == ["계란"]
