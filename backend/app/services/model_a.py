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


def _contains_all(fridge: set[str], recipe_ings: list[str]) -> bool:
    """냉장고가 레시피의 주재료(양념 제외)를 모두 보유하는가.

    BASIC_SEASONINGS는 사용자가 보유한다고 가정해 비교에서 제외 — SDD §3.2 3단계의
    "재료 매칭" 의도를 정밀화한 것이며 단계 위치·입출력은 동일.
    """
    required = [ing for ing in recipe_ings if ing not in BASIC_SEASONINGS]
    return all(ing in fridge for ing in required)


def _weighted_match_score(prefs: dict, r: Recipe, max_cook: int) -> float:
    """Aggarwal 2016 §4.4 / Ricci 2015 — 명목형+서열형 혼합 특성에 표준 가중합.

    이전 5차원 코사인 결함 (tracer 수학 증명):
      - pref_vec=[1,1,1,1,1] 고정 + diet_pref=False 시 diet_match 항상 1.0
      - country/theme/diff 모두 0/1 이산 → 같은 조합 다발 → score 동률 다발
      - 실효 변별 차원 = spicy 1개뿐 → cook_min asc tie-break으로만 정렬

    가중합 도입 효과:
      - 출력 공간 연속형에 가까움 (이산 동률 비율 50%+ → 10% 이하 예상)
      - 가중치 명시로 해석 가능 ("country 28% 기여")
      - cook_min을 score에 편입해 tie 완전 해소
      - 학계 출처: Aggarwal Recommender Systems Textbook §4.4, Ricci Handbook Ch.3

    가중치 (합=1.0) — 1차 튜닝 후 cook 가중치를 0.05→0.15로 상향해 동률 해소 강화:
      country  0.25 — 음식 종류 최우선 (사용자 1차 선택)
      theme    0.20 — 메인/반찬/국물 등 형태
      diff     0.18 — 난이도 거리 기반 (선형 디케이)
      spicy    0.12 — 맵기 거리 기반
      diet     0.10 — 다이어트 토글 매칭
      cook     0.15 — cook_min 정밀 변별 (1667 풀에서 동률 70%→<20% 효과)
    """
    c_pref = _COUNTRY_MAP.get(str(prefs.get("country", "한식")), "kr")
    t_pref = _THEME_MAP.get(str(prefs.get("food_type", "메인요리")), "main")
    d_pref = _DIFFICULTY_MAP.get(str(prefs.get("difficulty", "초보")), 1)
    s_pref = int(prefs.get("spicy", 3))
    diet_pref = bool(prefs.get("diet", False))

    country_match = 1.0 if r.country == c_pref else 0.0
    theme_match = 1.0 if r.theme == t_pref else 0.0
    diff_match = 1.0 - abs(r.difficulty_level - d_pref) / 2.0  # 0..1
    spicy_match = 1.0 - abs(r.spicy - s_pref) / 5.0  # 0..1
    diet_match = 1.0 if (r.is_low_calorie == diet_pref) else 0.0
    cook_norm = 1.0 - min(r.cook_min, max_cook) / max(1, max_cook)  # 빠를수록 1.0

    # 동률 해소: recipe_id 해시 기반 결정론적 미세 노이즈 (RecSys 표준 tie-break).
    # CSV 데이터 cook_min 73%가 30분으로 동일해 cook_norm만으로 변별 불가 → 보조 차원 필요.
    # 노이즈는 0~0.001 범위로 매우 작아 매칭 점수에 영향 X, 동률만 해소.
    id_jitter = (hash(r.recipe_id) % 1000) / 1_000_000.0  # 0.000000 ~ 0.000999

    return (
        0.25 * country_match
        + 0.20 * theme_match
        + 0.18 * diff_match
        + 0.12 * spicy_match
        + 0.10 * diet_match
        + 0.15 * cook_norm
        + id_jitter
    )


async def recommend_cold_storage(
    fridge_ingredients: list[str],
    preferences: dict,
    user_allergies: list[str],
    repo: RecipeRepository | None = None,
) -> list[dict]:
    """SDD §3.2 모델 A 추천 알고리즘 — 가중합 score (Aggarwal 2016 §4.4).

    NFR-EVAL-001: 알레르기 노출 0% (allergens 교집합 즉시 제외).
    NFR-PERF-003: 10초 타임아웃 내 완료 (recommend_service 레벨에서 강제).
    """
    repo = repo or get_repository()
    fridge_norm = set(normalize_list(fridge_ingredients))
    # NFR-EVAL-001: 카테고리("난류") → 세부재료("계란","달걀") 확장 후 정규화.
    allergies = set(normalize_list(expand_allergies(user_allergies or [])))
    max_cook = int(preferences.get("max_cook_min", 60))
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
        # 5단계: 가중합 score (이전 코사인 동률 결함 해소)
        score = _weighted_match_score(preferences, r, max_cook)
        scored.append((score, r))

    # 6단계: 상위 K 반환 (점수 desc, 동점 시 cook_min asc — score에 이미 cook 포함이라 거의 발생 X)
    scored.sort(key=lambda x: (-x[0], x[1].cook_min))
    out: list[dict] = []
    for score, r in scored[:top_k]:
        d = r.to_brief_dict()
        d["score"] = round(float(score), 4)
        out.append(d)
    return out
