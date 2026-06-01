"""레시피 인메모리 리포지토리 + 시드 데이터 (개발/테스트용).

운영에서는 DB로 교체. SDD §3.1 RecipeRepository 인터페이스 유지.
"""

from __future__ import annotations

from app.core.synonym_map import normalize_list
from app.models.recipe import Recipe


def _r(
    rid: str,
    name: str,
    ings: list[str],
    *,
    cook: int = 25,
    spicy: int = 1,
    diff: int = 1,
    low: bool = False,
    country: str = "kr",
    theme: str = "main",
    allergens: list[str] | None = None,
) -> Recipe:
    return Recipe(
        recipe_id=rid,
        name=name,
        whole_ingredients=normalize_list(ings),
        cook_min=cook,
        spicy=spicy,
        difficulty_level=diff,
        is_low_calorie=low,
        country=country,
        theme=theme,
        allergens=normalize_list(allergens or []),
    )


# 시드 레시피 — Model A·B 골든셋 회귀 테스트 가능 규모(30+개)
SEED_RECIPES: list[Recipe] = [
    _r("r001", "계란말이", ["계란", "대파", "소금"], cook=10, spicy=1, diff=1, allergens=["계란"]),
    _r("r002", "두부조림", ["두부", "간장", "고추", "마늘"], cook=20, spicy=3, diff=1, allergens=["대두"]),
    _r("r003", "김치찌개", ["김치", "돼지고기", "두부", "대파"], cook=30, spicy=4, diff=2, theme="soup", allergens=["돼지고기", "대두"]),
    _r("r004", "된장찌개", ["된장", "두부", "감자", "양파", "대파"], cook=25, spicy=2, diff=1, theme="soup", allergens=["대두"]),
    _r("r005", "제육볶음", ["돼지고기", "고추장", "양파", "대파", "마늘"], cook=25, spicy=5, diff=2, allergens=["돼지고기"]),
    _r("r006", "닭갈비", ["닭고기", "고추장", "양파", "양배추", "고구마"], cook=30, spicy=4, diff=2, allergens=["닭고기"]),
    _r("r007", "닭볶음탕", ["닭고기", "감자", "당근", "양파", "고추장"], cook=40, spicy=4, diff=2, theme="soup", allergens=["닭고기"]),
    _r("r008", "소고기무국", ["소고기", "무", "대파", "간장"], cook=30, spicy=1, diff=2, theme="soup", allergens=["소고기"]),
    _r("r009", "비빔밥", ["밥", "당근", "시금치", "버섯", "계란", "고추장"], cook=20, spicy=2, diff=1, allergens=["계란"]),
    _r("r010", "김치볶음밥", ["밥", "김치", "계란", "대파"], cook=15, spicy=3, diff=1, allergens=["계란"]),
    _r("r011", "잡채", ["면", "소고기", "버섯", "당근", "시금치", "간장"], cook=40, spicy=1, diff=3, allergens=["소고기", "대두"]),
    _r("r012", "떡볶이", ["떡", "고추장", "어묵", "대파"], cook=20, spicy=4, diff=1, allergens=["밀", "어류"]),
    _r("r013", "순두부찌개", ["두부", "고춧가루", "대파", "마늘", "계란"], cook=20, spicy=4, diff=1, theme="soup", allergens=["대두", "계란"]),
    _r("r014", "감자조림", ["감자", "간장", "마늘", "고추"], cook=25, spicy=2, diff=1, theme="side", allergens=["대두"]),
    _r("r015", "콩나물국", ["콩나물", "대파", "마늘"], cook=15, spicy=1, diff=1, theme="soup", low=True, allergens=["대두"]),
    _r("r016", "미역국", ["미역", "소고기", "마늘", "간장"], cook=30, spicy=1, diff=2, theme="soup", allergens=["소고기", "대두"]),
    _r("r017", "샐러드", ["상추", "양파", "올리브유", "치즈"], cook=10, spicy=1, diff=1, low=True, country="west", theme="side", allergens=["우유"]),
    _r("r018", "파스타", ["면", "올리브유", "마늘", "치즈"], cook=20, spicy=1, diff=2, country="west", allergens=["밀", "우유"]),
    _r("r019", "토마토파스타", ["면", "토마토", "마늘", "올리브유"], cook=25, spicy=1, diff=2, country="west", allergens=["밀"]),
    _r("r020", "까르보나라", ["면", "계란", "치즈", "돼지고기"], cook=20, spicy=1, diff=2, country="west", allergens=["밀", "계란", "우유", "돼지고기"]),
    _r("r021", "스테이크", ["소고기", "올리브유", "마늘"], cook=15, spicy=1, diff=3, country="west", allergens=["소고기"]),
    _r("r022", "치킨샐러드", ["닭고기", "상추", "양파", "올리브유"], cook=20, spicy=1, diff=1, low=True, country="west", theme="side", allergens=["닭고기"]),
    _r("r023", "마파두부", ["두부", "돼지고기", "고추", "마늘", "대파"], cook=25, spicy=5, diff=2, country="cn", allergens=["대두", "돼지고기"]),
    _r("r024", "짜장면", ["면", "양파", "돼지고기", "감자"], cook=30, spicy=1, diff=2, country="cn", allergens=["밀", "돼지고기", "대두"]),
    _r("r025", "탕수육", ["돼지고기", "당근", "양파", "식용유"], cook=40, spicy=1, diff=3, country="cn", allergens=["돼지고기"]),
    _r("r026", "초밥", ["쌀", "어류", "김"], cook=30, spicy=1, diff=3, country="jp", allergens=["어류"]),
    _r("r027", "우동", ["면", "간장", "대파", "계란"], cook=15, spicy=1, diff=1, theme="soup", country="jp", allergens=["밀", "대두", "계란"]),
    _r("r028", "오므라이스", ["밥", "계란", "양파", "당근"], cook=20, spicy=1, diff=2, country="jp", allergens=["계란"]),
    _r("r029", "규동", ["밥", "소고기", "양파", "간장"], cook=20, spicy=1, diff=1, country="jp", allergens=["소고기", "대두"]),
    _r("r030", "라멘", ["면", "돼지고기", "계란", "대파"], cook=30, spicy=2, diff=2, theme="soup", country="jp", allergens=["밀", "돼지고기", "계란"]),
    _r("r031", "야채볶음", ["양파", "당근", "버섯", "간장"], cook=15, spicy=1, diff=1, low=True, theme="side", allergens=["대두"]),
    _r("r032", "감자전", ["감자", "양파", "식용유"], cook=20, spicy=1, diff=1, theme="side"),
    _r("r033", "김밥", ["밥", "김", "당근", "계란", "시금치"], cook=30, spicy=1, diff=2, allergens=["계란"]),
    _r("r034", "라면", ["면", "계란", "대파"], cook=10, spicy=3, diff=1, theme="soup", allergens=["밀", "계란"]),
    _r("r035", "오이무침", ["오이", "고추", "마늘", "간장"], cook=10, spicy=3, diff=1, low=True, theme="side", allergens=["대두"]),
]


class RecipeRepository:
    """인메모리 레시피 저장소 (개발/테스트). DB 교체 시 동일 인터페이스 유지."""

    def __init__(self, recipes: list[Recipe] | None = None) -> None:
        self._recipes: list[Recipe] = list(recipes) if recipes is not None else list(SEED_RECIPES)
        self._by_id: dict[str, Recipe] = {r.recipe_id: r for r in self._recipes}

    def list_all(self) -> list[Recipe]:
        return list(self._recipes)

    def get(self, recipe_id: str) -> Recipe | None:
        return self._by_id.get(recipe_id)

    def whitelist_ids(self) -> set[str]:
        """Gemini citation 검증용 (NFR-EVAL-002 ≥95%)."""
        return set(self._by_id.keys())


_default_repo = RecipeRepository()


def get_repository() -> RecipeRepository:
    """기본 리포지토리 싱글톤 접근자 (FastAPI Depends 호환)."""
    return _default_repo


def set_repository(repo: RecipeRepository | None = None) -> None:
    """기본 리포지토리 교체 — lifespan에서 DB 로드 후 호출 (캡슐화 보존).

    이전: main.py가 `repo_mod._default_repo = ...` monkey-patch (code-reviewer HIGH 결함).
    공개 API로 분리해 의도가 명확하고 향후 테스트에서도 안전하게 교체 가능.

    repo=None: SEED_RECIPES를 담은 기본 RecipeRepository로 재설정 (테스트 teardown 용).
    """
    global _default_repo  # noqa: PLW0603 — 모듈 전역 교체가 의도된 동작
    _default_repo = repo if repo is not None else RecipeRepository()
