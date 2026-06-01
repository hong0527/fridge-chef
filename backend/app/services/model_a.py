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
    """레시피 → 사용자 선호 기준 5차원 정규화 벡터 (모든 차원 0~1 동치/거리 매칭).

    차원 (모두 사용자 선호 대비 점수, 1=완벽 일치, 0=완전 불일치):
      0. spicy_match    — 1 - |pref - recipe| / 5  (거리 기반)
      1. diff_match     — 동치 0|1 (이전 0.333 floor 제거 — tracer CRITICAL 수정)
      2. diet_match     — diet=True면 동치, diet=False면 항상 1 (다이어트 비활성 시 무관)
      3. country_match  — 동치 0|1
      4. theme_match    — 동치 0|1

    이전 결함(model_a.py:65 difficulty_level/3.0): 사용자 "고급"(1.0) vs 레시피 "초보"(0.333)
    곱 0.333이 country/theme 일치 1.0 두 차원에 압도되던 문제를 동치 매칭으로 해소.
    """
    spicy_pref = int(prefs.get("spicy", 3))
    diff_pref = _DIFFICULTY_MAP.get(str(prefs.get("difficulty", "초보")), 1)
    country_pref = _COUNTRY_MAP.get(str(prefs.get("country", "한식")), "kr")
    theme_pref = _THEME_MAP.get(str(prefs.get("food_type", "메인요리")), "main")
    diet_pref = bool(prefs.get("diet", False))

    spicy_match = 1.0 - abs(spicy_pref - r.spicy) / 5.0
    diff_match = 1.0 if r.difficulty_level == diff_pref else 0.0
    diet_match = (1.0 if r.is_low_calorie else 0.0) if diet_pref else 1.0
    country_match = 1.0 if r.country == country_pref else 0.0
    theme_match = 1.0 if r.theme == theme_pref else 0.0
    return [spicy_match, diff_match, diet_match, country_match, theme_match]


def _vec_from_prefs(prefs: dict) -> list[float]:
    """사용자 선호 → 5차원 정규화 벡터.

    모든 차원이 "자기 자신과의 동치"이므로 항상 1.0 — 레시피 벡터의 각 *_match와
    코사인 곱이 가능해 매칭 정도가 점수에 직접 반영된다.
    """
    return [1.0, 1.0, 1.0, 1.0, 1.0]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _ingredient_overlap_ratio(fridge: set[str], recipe_ings: list[str]) -> float:
    """냉장고와 레시피 주재료의 매칭 비율 (0~1) — Jaccard-like overlap.

    Aggarwal 2016 §4.5: hard `contains_all` 대신 부분 매칭 허용 (overlap ratio).
    BASIC_SEASONINGS는 사용자 보유 가정으로 비교에서 제외.

    예: 사용자 7개 재료 + 레시피 주재료 5개 → 3개 매칭이면 3/5 = 0.6
    """
    required = [ing for ing in recipe_ings if ing not in BASIC_SEASONINGS]
    if not required:
        return 1.0
    matched = sum(1 for ing in required if ing in fridge)
    return matched / len(required)


def _weighted_match_score(prefs: dict, r: Recipe, max_cook: int, overlap: float) -> float:
    """Aggarwal 2016 §4.4 — 명목형+서열형 혼합 특성에 표준 가중합.

    가중치 (합=1.0):
      ingredient_overlap 0.30 — 보유 재료 매칭 비율 (가장 중요)
      country            0.20 — 음식 종류
      theme              0.15 — 메인/반찬/국물 등 형태
      difficulty         0.13 — 난이도 거리
      spicy              0.10 — 맵기 거리
      diet               0.07 — 다이어트 토글
      cook               0.05 — 빠를수록 가산

    + recipe_id 해시 jitter (0~0.001) — 동률 결정론 해소 (RecSys 표준 score perturbation).
    """
    c_pref = _COUNTRY_MAP.get(str(prefs.get("country", "한식")), "kr")
    t_pref = _THEME_MAP.get(str(prefs.get("food_type", "메인요리")), "main")
    d_pref = _DIFFICULTY_MAP.get(str(prefs.get("difficulty", "초보")), 1)
    s_pref = int(prefs.get("spicy", 3))
    diet_pref = bool(prefs.get("diet", False))

    country_match = 1.0 if r.country == c_pref else 0.0
    theme_match = 1.0 if r.theme == t_pref else 0.0
    diff_match = 1.0 - abs(r.difficulty_level - d_pref) / 2.0
    spicy_match = 1.0 - abs(r.spicy - s_pref) / 5.0
    diet_match = 1.0 if (r.is_low_calorie == diet_pref) else 0.0
    cook_norm = 1.0 - min(r.cook_min, max_cook) / max(1, max_cook)
    id_jitter = (hash(r.recipe_id) % 1000) / 1_000_000.0

    return (
        0.30 * overlap
        + 0.20 * country_match
        + 0.15 * theme_match
        + 0.13 * diff_match
        + 0.10 * spicy_match
        + 0.07 * diet_match
        + 0.05 * cook_norm
        + id_jitter
    )


# 부분 매칭 임계값 — 최소 50% 재료 보유 시 후보로 고려 (Aggarwal §4.5 Jaccard threshold).
_OVERLAP_THRESHOLD = 0.5


async def recommend_cold_storage(
    fridge_ingredients: list[str],
    preferences: dict,
    user_allergies: list[str],
    repo: RecipeRepository | None = None,
) -> list[dict]:
    """SDD §3.2 모델 A — Stratified Top-K + Jaccard overlap + 가중합 score.

    개선 (Issue #40):
    1. contains_all hard filter → ingredient overlap ratio (≥ 0.5) — 부분 매칭 허용
    2. country/theme/difficulty Stratified retrieval — 사용자 선호 일치 후보 우선
    3. 가중합 score + jitter — 동률 결정론 해소

    NFR-EVAL-001 알레르기 0% / NFR-PERF-003 10초.
    """
    repo = repo or get_repository()
    if not fridge_ingredients:
        return []

    fridge_norm = set(normalize_list(fridge_ingredients))
    allergies = set(normalize_list(expand_allergies(user_allergies or [])))
    max_cook = int(preferences.get("max_cook_min", 60))
    top_k = settings.top_k_model_a

    c_pref = _COUNTRY_MAP.get(str(preferences.get("country", "한식")), "kr")
    t_pref = _THEME_MAP.get(str(preferences.get("food_type", "메인요리")), "main")
    d_pref = _DIFFICULTY_MAP.get(str(preferences.get("difficulty", "초보")), 1)

    # 1단계: base 필터 (안전·핵심 — overlap ≥ 0.4, 알레르기 차단, 조리시간, 매운맛)
    # 매운맛 hard filter — 사용자 시연 피드백 ('매운맛 5 선택해도 1점 레시피 나옴').
    # 차이 2 이내 통과 ("5점 원하는데 3점은 OK, 1~2점은 차단").
    s_pref_int = int(preferences.get("spicy", 3))
    base_pool: list[tuple[Recipe, float]] = []
    for r in repo.list_all():
        if allergies and any(a in allergies for a in r.allergens):
            continue
        if r.cook_min > max_cook:
            continue
        # 매운맛 비대칭 hard filter — '안 매운(1·2)' 사용자에 매콤(3)이 노출되는 의도 위반 차단.
        # spicy ≤ 2 → 차이 1 이내, spicy ≥ 3 → 차이 2 이내.
        spicy_tol = 1 if s_pref_int <= 2 else 2
        if abs(r.spicy - s_pref_int) > spicy_tol:
            continue
        # difficulty hard filter — 초보 사용자에게 고급 추천 침묵 차단 (MAJOR).
        # 차이 1 이내만 통과 (초보→중급 OK, 초보→고급 차단).
        if abs(r.difficulty_level - d_pref) > 1:
            continue
        overlap = _ingredient_overlap_ratio(fridge_norm, r.whole_ingredients)
        if overlap < _OVERLAP_THRESHOLD:
            continue
        base_pool.append((r, overlap))

    # 2단계: Stratified retrieval — 사용자 선호 일치 단계로 풀 좁힘
    # tier3에 theme 조건 강제 추가 — '한식 디저트' 요청 시 '한식 메인' 침묵 폴백 차단 (CRITICAL #1).
    # difficulty 폴백은 가중합 score에 맡김.
    tier1 = [(r, o) for r, o in base_pool
             if r.country == c_pref and r.theme == t_pref and r.difficulty_level == d_pref]
    tier2 = [(r, o) for r, o in base_pool if r.country == c_pref and r.theme == t_pref]
    tier3 = [(r, o) for r, o in base_pool if r.country == c_pref and r.theme == t_pref]

    selected: list[tuple[Recipe, float]] = []
    seen_ids: set[str] = set()
    # base_pool 폴백 제거 — "중식 선택했는데 일식 나옴" 사용자 침묵 위반 차단(CRITICAL #C2).
    # tier3까지 = 사용자 country 일치 강제. 후보 부족하면 빈 결과 반환이 더 정직.
    for tier in (tier1, tier2, tier3):
        for r, o in tier:
            if r.recipe_id not in seen_ids:
                selected.append((r, o))
                seen_ids.add(r.recipe_id)
        if len(selected) >= top_k:
            break

    # 3단계: 가중합 score + 정렬
    scored = [(_weighted_match_score(preferences, r, max_cook, o), r) for r, o in selected]
    scored.sort(key=lambda x: (-x[0], x[1].cook_min))

    out: list[dict] = []
    for score, r in scored[:top_k]:
        d = r.to_brief_dict()
        d["score"] = round(float(score), 4)
        out.append(d)
    return out
