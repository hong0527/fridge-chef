"""모델 A — 냉털 추천 (코사인 유사도 기반).

SDD §3.2 모델 A 시퀀스:
1. SYNONYM_MAP 정규화
2. 알레르기 재료 포함 레시피 제외 (FR-007, NFR-EVAL-001 = 알레르기 노출 0%)
3. contains_all_ingredients 하드 필터 (냉장고 ⊇ recipe.whole_ingredients)
4. 최대 조리시간 초과 제외
5. 코사인 유사도 (맵기·난이도·저칼로리·나라·테마 5차원 벡터)
6. 상위 10개 반환 (Top-K = TOP_K_MODEL_A)

NFR-PERF-003: 추천 응답 ≤10s (단일 모델 기준 < 1s 목표).
"""

from __future__ import annotations

import math

from app.core.config import settings
from app.core.synonym_map import normalize_list
from app.models.recipe import Recipe
from app.models.recipe_repository import RecipeRepository, get_repository

# 난이도 한글 → 숫자
_DIFFICULTY_MAP: dict[str, int] = {"초보": 1, "중급": 2, "고급": 3}
# 나라 한글 → 코드
_COUNTRY_MAP: dict[str, str] = {
    "한식": "kr",
    "중식": "cn",
    "일식": "jp",
    "양식": "west",
    "기타": "etc",
}
# 테마 한글 → 코드
_THEME_MAP: dict[str, str] = {
    "메인요리": "main",
    "반찬": "side",
    "국물": "soup",
    "디저트": "dessert",
    "음료": "drink",
}


def _vec_from_recipe(r: Recipe) -> list[float]:
    """레시피 → 5차원 정규화 벡터.

    차원: [맵기, 난이도, 저칼로리, 나라(원-핫 평균치 대신 해시 정규화), 테마(동일)].
    """
    country_code = {"kr": 0.2, "cn": 0.4, "jp": 0.6, "west": 0.8, "etc": 1.0}.get(r.country, 0.5)
    theme_code = {"main": 0.2, "side": 0.4, "soup": 0.6, "dessert": 0.8, "drink": 1.0}.get(r.theme, 0.5)
    return [
        r.spicy / 5.0,
        r.difficulty_level / 3.0,
        1.0 if r.is_low_calorie else 0.0,
        country_code,
        theme_code,
    ]


def _vec_from_prefs(prefs: dict) -> list[float]:
    spicy = int(prefs.get("spicy", 3))
    diff = _DIFFICULTY_MAP.get(str(prefs.get("difficulty", "초보")), 1)
    diet = bool(prefs.get("diet", False))
    country = _COUNTRY_MAP.get(str(prefs.get("country", "한식")), "kr")
    theme = _THEME_MAP.get(str(prefs.get("food_type", "메인요리")), "main")
    country_code = {"kr": 0.2, "cn": 0.4, "jp": 0.6, "west": 0.8, "etc": 1.0}[country]
    theme_code = {"main": 0.2, "side": 0.4, "soup": 0.6, "dessert": 0.8, "drink": 1.0}[theme]
    return [
        spicy / 5.0,
        diff / 3.0,
        1.0 if diet else 0.0,
        country_code,
        theme_code,
    ]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _contains_all(fridge: set[str], recipe_ings: list[str]) -> bool:
    """냉장고가 레시피의 모든 재료를 보유하는가."""
    return all(ing in fridge for ing in recipe_ings)


async def recommend_cold_storage(
    fridge_ingredients: list[str],
    preferences: dict,
    user_allergies: list[str],
    repo: RecipeRepository | None = None,
) -> list[dict]:
    """SDD §3.2 모델 A 추천 알고리즘.

    NFR-EVAL-001: 알레르기 노출 0% (allergens 교집합 즉시 제외).
    NFR-PERF-003: 10초 타임아웃 내 완료 (recommend_service 레벨에서 강제).
    """
    repo = repo or get_repository()
    fridge_norm = set(normalize_list(fridge_ingredients))
    allergies = set(normalize_list(user_allergies or []))
    max_cook = int(preferences.get("max_cook_min", 60))
    pref_vec = _vec_from_prefs(preferences)
    top_k = settings.top_k_model_a

    scored: list[tuple[float, Recipe]] = []
    for r in repo.list_all():
        # 2단계: 알레르기 하드컷
        if allergies and any(a in allergies for a in r.allergens):
            continue
        # 3단계: 하드 필터 (냉장고 ⊇ 레시피)
        if not _contains_all(fridge_norm, r.whole_ingredients):
            continue
        # 4단계: 조리시간
        if r.cook_min > max_cook:
            continue
        # 5단계: 코사인 유사도
        score = _cosine(pref_vec, _vec_from_recipe(r))
        scored.append((score, r))

    # 6단계: 상위 K 반환 (점수 desc, 동점 시 cook_min asc)
    scored.sort(key=lambda x: (-x[0], x[1].cook_min))
    out: list[dict] = []
    for score, r in scored[:top_k]:
        d = r.to_brief_dict()
        d["score"] = round(float(score), 4)
        out.append(d)
    return out
