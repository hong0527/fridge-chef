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

import hashlib
import math

from app.core.allergy_map import expand_allergies
from app.core.config import settings
from app.core.synonym_map import normalize_list
from app.models.recipe import Recipe
from app.models.recipe_repository import RecipeRepository, get_repository
from app.services.context_expander import expand_context

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
# 테마 한글 → 코드 (사용자 입력 다양성 흡수: '찌개'·'탕'·'국' 모두 soup 매핑)
# tracer CRITICAL: 이전엔 '찌개' 키 누락으로 한식 찌개 시연 시 model_b 후보풀 전량 차단.
_THEME_MAP: dict[str, str] = {
    "메인요리": "main",
    "메인": "main",
    "밥": "main",
    "반찬": "side",
    "나물": "side",
    "국물": "soup",
    "국": "soup",
    "찌개": "soup",
    "탕": "soup",
    "디저트": "dessert",
    "간식": "dessert",
    "음료": "drink",
    "차": "drink",
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
    # diet_pref=False 인 사용자에게 저칼로리/일반 모두 1.0 (다이어트 비활성).
    # diet_pref=True 인 사용자에게만 저칼로리 1.0, 일반 0.0 (critic HIGH-2: 이전 동치 매칭 모순).
    diet_match = 1.0 if (not diet_pref or r.is_low_calorie) else 0.0
    cook_norm = 1.0 - min(r.cook_min, max_cook) / max(1, max_cook)
    # 결정론적 jitter — Python hash() 는 PYTHONHASHSEED 미고정 시 프로세스마다 변경되어
    # 시연 중 새로고침마다 동률 순서가 흔들리는 비결정성 발생 (critic F2 CRITICAL).
    # hashlib.md5 는 프로세스 무관 결정론 보장.
    id_jitter = int(hashlib.md5(r.recipe_id.encode()).hexdigest()[:6], 16) % 1000 / 1_000_000.0

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


# 부분 매칭 임계값 — Aggarwal §4.5 Jaccard threshold.
# 1.0 (전부 보유) 은 운영 1667 레시피에 대해 흔한 재료(3~5개) 입력 시 0~2 후보만 통과 →
# Model A 빈 응답 위험 (code-reviewer CRITICAL-1). 0.6 은 60% 이상 보유 시 통과 →
# Model A 의미 있는 후보풀 (~30~80) 확보, 부족 비율은 score 가중합에서 자연 페널티.
# Model B 는 missing >= 1 별도 영역이므로 분리 유지 (missing=0 vs missing>=1 자연 분리).
_OVERLAP_THRESHOLD = 0.6

# 자연어 의미검색 후보 주입 개수 런타임 오버라이드 (평가 ablation 용). None 이면 settings 사용.
_NL_RETRIEVAL_K_OVERRIDE: int | None = None


def set_nl_retrieval_k(k: int | None) -> None:
    """평가용 — 자연어 retrieval 주입 개수를 런타임 강제. None 이면 설정값 복원."""
    global _NL_RETRIEVAL_K_OVERRIDE
    _NL_RETRIEVAL_K_OVERRIDE = k


def _nl_retrieval_k() -> int:
    return (
        _NL_RETRIEVAL_K_OVERRIDE
        if _NL_RETRIEVAL_K_OVERRIDE is not None
        else settings.nl_retrieval_k
    )


async def recommend_cold_storage(
    fridge_ingredients: list[str],
    preferences: dict,
    user_allergies: list[str],
    repo: RecipeRepository | None = None,
    user_context: str = "",
) -> list[dict]:
    """SDD §3.2 모델 A — Stratified Top-K + Jaccard overlap + 가중합 score.

    개선 (Issue #40):
    1. contains_all hard filter → ingredient overlap ratio (≥ 0.5) — 부분 매칭 허용
    2. country/theme/difficulty Stratified retrieval — 사용자 선호 일치 후보 우선
    3. 가중합 score + jitter — 동률 결정론 해소

    개선 (Issue #72): TF-IDF 코사인 유사도 추가 (0.20 가중치) — user_context 자연어 점수 반영.
    최종 score = 0.80 * 가중합(선호+overlap) + 0.20 * tfidf(보유재료+user_context vs 1667 코퍼스).
    Salton & McGill 1983 TF-IDF + Aggarwal 2016 §4.5 Content-Based hybrid 표준.

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
    # tier3 == tier2 dead code 제거 (Critic MAJOR #2). 단계적 폴백으로 후보 풀 확대.
    # 사용자 의도 '중식→한식 차단' 보존을 위해 country는 모든 tier에서 강제 유지.
    # theme/difficulty 만 단계적으로 완화해 후보 풀을 1~3개 → 5~10개로 확대 →
    # TF-IDF 가중치 0.20 이 의미 있는 변별력을 발휘할 수 있는 후보 수 확보.
    tier1 = [(r, o) for r, o in base_pool
             if r.country == c_pref and r.theme == t_pref and r.difficulty_level == d_pref]
    tier2 = [(r, o) for r, o in base_pool if r.country == c_pref and r.theme == t_pref]
    tier3 = [(r, o) for r, o in base_pool if r.country == c_pref]  # theme 완화

    selected: list[tuple[Recipe, float]] = []
    seen_ids: set[str] = set()
    # base_pool(전체) 폴백 제거 — "중식 선택했는데 일식 나옴" 사용자 침묵 위반 차단(CRITICAL #C2).
    # country 일치 강제. 후보 부족하면 빈 결과 반환이 더 정직.
    for tier in (tier1, tier2, tier3):
        for r, o in tier:
            if r.recipe_id not in seen_ids:
                selected.append((r, o))
                seen_ids.add(r.recipe_id)
        if len(selected) >= top_k:
            break

    # 3단계: 가중합 + TF-IDF 임베딩 코사인 유사도 결합 (Issue #72 — AI 기반 추천 강화).
    # tfidf_score 는 사용자 보유 재료 + user_context 자연어를 1667 코퍼스 벡터 공간에서 매칭.
    # 가중치 0.20 = 학계 표준 (Aggarwal §4.4 weighted sum + content-based hybrid).
    # user_context 는 expand_context 로 코퍼스 도메인 키워드 확장 후 입력
    # (Salton & McGill 1983 §6 Query Expansion — OOV 어휘 흡수).
    from app.services.embedding_service import score_query
    expanded_ctx = expand_context(user_context)
    query_text = f"{' '.join(fridge_norm)} {expanded_ctx}".strip()
    # nl_text: 의미 임베딩 백엔드가 쓸 순수 자연어 (재료 토큰 배제). TF-IDF 는 query_text 사용.
    tfidf_scores = score_query(query_text, nl_text=user_context)

    # 3.5단계: 자연어 의미검색 후보 생성 주입 (NL retrieval) — Issue #72 후속.
    # 진단(evaluate_semantic_nl.py): 자연어 정답의 다수가 재료 overlap·theme 필터에서
    # 후보 진입 전 탈락 → 재정렬만으로 회복 불가. user_context 의미 유사 상위 K개를
    # 안전/선호 필터(알레르기·국가·조리시간·맵기·난이도)만 적용해 후보풀에 합류시킨다.
    # overlap·theme 은 우회(의미 의도가 재료/형태 제약보다 우선). 알레르기 0%·국가 선호는
    # 유지 — '양식 선호 + 한식 자연어 → 양식만' 회귀(test_nl_recommendation) 보호.
    nl_k = _nl_retrieval_k()
    if nl_k > 0 and user_context.strip() and tfidf_scores:
        ranked = sorted(
            repo.list_all(),
            key=lambda r: tfidf_scores.get(r.recipe_id, 0.0),
            reverse=True,
        )
        added = 0
        for r in ranked:
            if added >= nl_k:
                break
            if r.recipe_id in seen_ids:
                continue
            if allergies and any(a in allergies for a in r.allergens):
                continue  # NFR-EVAL-001 알레르기 0% — 절대 우회 금지.
            if r.cook_min > max_cook:
                continue
            if abs(r.spicy - s_pref_int) > (1 if s_pref_int <= 2 else 2):
                continue
            if abs(r.difficulty_level - d_pref) > 1:
                continue
            if r.country != c_pref:
                continue  # 국가 선호 유지 (회귀 보호).
            overlap = _ingredient_overlap_ratio(fridge_norm, r.whole_ingredients)
            # makeable 게이트 — 재료가 너무 안 겹치면 '냉털(지금 만들기)'에 부적합이라 주입 제외
            # (감사 지적: 무제한 주입이 missing 과다 후보를 Model A에 섞는 계약위반 방지).
            if overlap < settings.nl_retrieval_overlap_floor:
                continue
            selected.append((r, overlap))
            seen_ids.add(r.recipe_id)
            added += 1

    # TF-IDF 코사인은 짧은 쿼리에서 0.0~0.15 범위에 집중 — 가중합(0.3~0.95) 대비 스케일 불일치.
    # 후보 풀 내 min-max 정규화로 TF-IDF 신호가 0.20 가중치만큼 실제 효과 발휘 (code-reviewer HIGH-1).
    sel_tfidf = [tfidf_scores.get(r.recipe_id, 0.0) for r, _ in selected]
    tmin, tmax = (min(sel_tfidf), max(sel_tfidf)) if sel_tfidf else (0.0, 0.0)
    trange = tmax - tmin
    def _norm(rid: str) -> float:
        raw = tfidf_scores.get(rid, 0.0)
        # 분산이 거의 없으면(후보 동질·풀 크기 1) min-max 가 신호를 0으로 소멸시키던 버그 수정.
        # raw 값을 그대로 사용 → 랭킹엔 영향 없으나 의미 임베딩의 절대 신호를 보존.
        if trange < 1e-9:
            return raw
        return (raw - tmin) / trange
    # 자연어 점수 가중치 — settings.nl_weight (기본 0.20, ablation 으로 0.35 검증).
    w_nl = settings.nl_weight
    scored = [
        (
            (1.0 - w_nl) * _weighted_match_score(preferences, r, max_cook, o)
            + w_nl * _norm(r.recipe_id),
            r,
        )
        for r, o in selected
    ]
    scored.sort(key=lambda x: (-x[0], x[1].cook_min))

    # Model A = '재료 완비(missing==0)' 중 자연어 매칭 상위 — 지금 바로 만들 수 있는 요리.
    # missing>0 후보는 Model B(부족재료 1~5) 영역이므로 제외 → A·B 가 missing 수로 자연 분리되어
    # 같은 레시피가 양쪽에 동시 노출되는 중복 버그를 원천 차단. scored 전체에서 완비 후보를 top_k 까지 수집.
    out: list[dict] = []
    for score, r in scored:
        main_ings = [ing for ing in r.whole_ingredients if ing not in BASIC_SEASONINGS]
        missing = [ing for ing in main_ings if ing not in fridge_norm]
        if missing:
            continue  # 재료 부족 → Model B 로 (A 에서 제외)
        d = r.to_brief_dict()
        d["score"] = round(float(score), 4)
        d["have"] = [ing for ing in main_ings if ing in fridge_norm]
        d["missing"] = []
        out.append(d)
        if len(out) >= top_k:
            break

    # Gemini 자연어 reason 생성 — Top-3 만 Gemini 호출 (비용 절감 + 응답 시간 단축).
    # 사용자 신뢰성 향상 (Model A 도 Model B 와 동일한 UX, "왜" 추천됐는지 명시).
    # 시연 시 발표자가 "AI 가 골라준 이유" 를 시각 자료로 활용 가능.
    from app.services.gemini_client import gemini_reasons_for_model_a
    top3 = out[:3]
    gemini_reasons = None
    if top3:
        try:
            gemini_reasons = await gemini_reasons_for_model_a(top3, user_context)
        except Exception:  # noqa: BLE001 — 네트워크 의존, 폴백으로 안전.
            gemini_reasons = None
    for idx, d in enumerate(out):
        if idx < 3 and gemini_reasons and idx < len(gemini_reasons) and gemini_reasons[idx]:
            d["reason"] = gemini_reasons[idx]
        else:
            # 결정론 폴백 — Gemini 실패·타임아웃 또는 4~10번 후보 (cost 절감).
            # missing 유무로 분기 — 재료가 부족한데 '바로 만들 수 있다'고 거짓 안내하지 않음 (model_b 와 동일 정책).
            have_str = ", ".join(d["have"][:3]) or "냉장고 재료"
            missing_str = ", ".join(d["missing"][:2])
            if missing_str:
                d["reason"] = f"보유한 {have_str} 활용. {missing_str} 추가 시 완성됩니다."
            else:
                d["reason"] = f"보유한 {have_str} 만으로 바로 만들 수 있습니다."
    return out
