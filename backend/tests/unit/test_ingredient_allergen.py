"""_ingredient_has_allergen — false positive 방지 단위 테스트 (FP-001~007).

b4da656 커밋에서 false positive 수정을 주장했으나 자동화 테스트가 없었음.
이 파일이 그 검증을 담당한다.
"""

from scripts.import_real_recipes import _ingredient_has_allergen


class TestIngredientHasAllergenPositive:
    """정상 매칭 케이스 — 알레르기가 맞게 감지되어야 하는 경우."""

    # FP-001
    def test_chicken_breast_matches_chicken(self) -> None:
        assert _ingredient_has_allergen("닭가슴살", ["닭"]) is True

    # FP-002
    def test_pork_matches_pork(self) -> None:
        assert _ingredient_has_allergen("돼지고기", ["돼지"]) is True

    # FP-003
    def test_shrimp_paste_matches_shrimp(self) -> None:
        assert _ingredient_has_allergen("새우젓", ["새우"]) is True


class TestIngredientHasAllergenFalsePositive:
    """false positive 차단 케이스 — 알레르기가 없다고 판단해야 하는 경우."""

    # FP-004
    def test_chicken_feet_not_allergen_for_partial(self) -> None:
        assert _ingredient_has_allergen("닭발", ["발"]) is False

    # FP-005
    def test_pork_skin_not_allergen_for_partial(self) -> None:
        assert _ingredient_has_allergen("돼지껍데기", ["껍데기"]) is False

    # FP-006: 닭/돼지 접두사 없는 일반 재료에서도 substring 오탐 차단
    def test_sweet_potato_not_partial_match(self) -> None:
        assert _ingredient_has_allergen("고구마", ["구마"]) is False


class TestIngredientHasAllergenBoundary:
    """경계값 케이스."""

    # FP-007
    def test_empty_ingredient_returns_false(self) -> None:
        assert _ingredient_has_allergen("", ["계란"]) is False
