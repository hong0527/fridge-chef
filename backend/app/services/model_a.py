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

from app.core.allergy_map import expand_allergies
from app.core.config import settings
from app.core.synonym_map import normalize_list
from app.models.recipe import Recipe
from app.models.recipe_repository import RecipeRepository, get_repository

# 기본 양념·기름·물 — 사용자가 명시 입력하지 않아도 가정 (NFR-USE-001 편의).
# contains_all 비교와 model_b 보유/부족 분류에서 모두 제외해 추천 빈 결과 빈도를 줄임.
BASIC_SEASONINGS: frozenset[str] = frozenset({
    "소금", "설탕", "물", "후추",
    "식용유", "올리브유", "참기름", "들기름",
    "간장", "고추장", "된장",
})

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


def _vec_from_recipe(r: Recipe, prefs: dict) -> list[float]:
    """레시피 → 사용자 선호 기준 5차원 정규화 벡터.

    차원: [맵기, 난이도, 저칼로리, country_match(0|1), theme_match(0|1)].

    country/theme는 사용자 선호와 동치 여부로 인코딩 — ordinal 매핑(kr=0.2, cn=0.4...)이
    "한식·중식 거리 0.2 < 한식·양식 거리 0.6"처럼 명목형에 허위 순서를 부여하던 왜곡을 제거.
    SDD §3.2 "5차원 벡터 코사인" 텍스트 유지.
    """
    country_pref = _COUNTRY_MAP.get(str(prefs.get("country", "한식")), "kr")
    theme_pref = _THEME_MAP.get(str(prefs.get("food_type", "메인요리")), "main")
    return [
        r.spicy / 5.0,
        r.difficulty_level / 3.0,
        1.0 if r.is_low_calorie else 0.0,
        1.0 if r.country == country_pref else 0.0,
        1.0 if r.theme == theme_pref else 0.0,
    ]


def _vec_from_prefs(prefs: dict) -> list[float]:
    """사용자 선호 → 5차원 정규화 벡터.

    country/theme 차원은 "자기 자신과의 동치"이므로 항상 1.0 — 레시피 벡터의
    country_match/theme_match와 코사인 곱이 가능해 동치 시 점수 가산.
    """
    spicy = int(prefs.get("spicy", 3))
    diff = _DIFFICULTY_MAP.get(str(prefs.get("difficulty", "초보")), 1)
    diet = bool(prefs.get("diet", False))
    return [
        spicy / 5.0,
        diff / 3.0,
        1.0 if diet else 0.0,
        1.0,
        1.0,
    ]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _contains_all(fridge: set[str], recipe_ings: list[str]) -> bool:
    """냉장고가 레시피의 주재료(양념 제외)를 모두 보유하는가.

    BASIC_SEASONINGS는 사용자가 보유한다고 가정해 비교에서 제외 — SDD §3.2 3단계의
    "재료 매칭" 의도를 정밀화한 것이며 단계 위치·입출력은 동일.
    """
    required = [ing for ing in recipe_ings if ing not in BASIC_SEASONINGS]
    return all(ing in fridge for ing in required)


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
    # NFR-EVAL-001: 카테고리("난류") → 세부재료("계란","달걀") 확장 후 정규화.
    allergies = set(normalize_list(expand_allergies(user_allergies or [])))
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
        # 5단계: 코사인 유사도 (country/theme는 동치 매칭으로 인코딩 — ordinal 왜곡 제거)
        score = _cosine(pref_vec, _vec_from_recipe(r, preferences))
        scored.append((score, r))

    # 6단계: 상위 K 반환 (점수 desc, 동점 시 cook_min asc)
    scored.sort(key=lambda x: (-x[0], x[1].cook_min))
    out: list[dict] = []
    for score, r in scored[:top_k]:
        d = r.to_brief_dict()
        d["score"] = round(float(score), 4)
        out.append(d)
    return out
