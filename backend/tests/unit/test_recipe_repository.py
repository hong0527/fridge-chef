"""set_repository() / get_repository() 격리 패턴 테스트 (SR-001~002).

글로벌 상태(_default_repo)를 변경하는 API의 안전성을 검증한다.
autouse fixture가 각 테스트 후 원래 인스턴스를 복원해 테스트 간 격리를 보장한다.
"""

from __future__ import annotations

import pytest

from app.models.recipe import Recipe
from app.models.recipe_repository import (
    SEED_RECIPES,
    RecipeRepository,
    get_repository,
    set_repository,
)

_STUB_RECIPE = Recipe("stub001", "테스트요리", ["재료"], cook_min=5)


@pytest.fixture(autouse=True)
def restore_default_repo():
    """각 테스트 전 원본 인스턴스를 저장하고, 테스트 후 정확히 복원한다."""
    original = get_repository()
    yield
    set_repository(original)


class TestSetRepository:
    """SR-001~002: set_repository() / get_repository() 동작 검증."""

    def test_sr_001_custom_repo_is_returned_by_get(self) -> None:
        """SR-001 — 커스텀 repo 주입 시 get_repository()가 동일 객체를 반환.

        set_repository(custom) 후 get_repository() is custom 이어야 한다.
        """
        custom = RecipeRepository([_STUB_RECIPE])
        set_repository(custom)
        assert get_repository() is custom

    def test_sr_002_none_restores_default_without_error(self) -> None:
        """SR-002 — set_repository(None)은 오류 없이 SEED 기본 repo로 복귀.

        1) 빈 커스텀 repo로 교체 → get_repository()가 커스텀을 반환하는지 확인
        2) set_repository(None) 호출 (예외 없어야 함)
        3) get_repository()가 None이 아닌 유효한 RecipeRepository를 반환
        4) 복원된 repo가 SEED_RECIPES 전체를 포함(기본 카탈로그로 복귀)
        """
        empty_custom = RecipeRepository([])
        set_repository(empty_custom)
        assert get_repository() is empty_custom, "교체 확인 실패"

        set_repository(None)  # 예외 없이 실행돼야 함

        restored = get_repository()
        assert restored is not None, "None이 반환되면 안 됨"
        assert restored is not empty_custom, "커스텀 repo가 그대로이면 안 됨"
        assert len(restored.list_all()) == len(SEED_RECIPES), (
            f"기본 카탈로그 크기 불일치: 기대 {len(SEED_RECIPES)}, "
            f"실제 {len(restored.list_all())}"
        )
