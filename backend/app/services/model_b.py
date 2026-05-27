"""모델 B — 부족재료 추천 (복합 점수 + Gemini 선별).

SDD §3.2 모델 B 시퀀스:
1. SYNONYM_MAP 정규화
2. 알레르기·조리시간 필터
3. analyze_ingredients: 보유/부족 재료 분류
4. 소프트 필터: 부족 재료 ≤ MISSING_INGREDIENTS_MAX (기본 5)
5. 복합 점수 = 선호도×0.7 + 보유재료율×0.2 + 부족재료적음×0.1
6. 상위 10개 → Gemini 2.5 Flash가 3개 선별 + 한국어 추천 이유
7. citation_id 화이트리스트 검증 (NFR-EVAL-002 ≥95%)

NFR-PERF-003: 10s 타임아웃 (서비스 레벨에서 강제).
NFR-EVAL-001: 알레르기 0%.
"""

from __future__ import annotations

from app.core.allergy_map import expand_allergies
from app.core.config import settings
from app.core.synonym_map import normalize_list
from app.models.recipe import Recipe
from app.models.recipe_repository import RecipeRepository, get_repository
from app.services.gemini_client import gemini_select_top3
from app.services.model_a import (
    BASIC_SEASONINGS,
    _cosine,
    _vec_from_prefs,
    _vec_from_recipe,
)


def _analyze_ingredients(fridge: set[str], recipe_ings: list[str]) -> tuple[list[str], list[str]]:
    """양념을 제외한 주재료를 보유/부족으로 분류.

    "소금이 부족합니다" 같은 의미 없는 missing을 방지 — 사용자에게 표시되는 "이것만 더 사면"
    메시지가 자연스러워지고, missing 카운트가 max_missing 임계에 더 적합해진다.
    """
    main_ings = [ing for ing in recipe_ings if ing not in BASIC_SEASONINGS]
    have = [ing for ing in main_ings if ing in fridge]
    missing = [ing for ing in main_ings if ing not in fridge]
    return have, missing


def _composite_score(pref_sim: float, have_ratio: float, missing_count: int, max_missing: int) -> float:
    """SDD §3.2 5단계 가중치: 0.7 / 0.2 / 0.1."""
    missing_penalty = max(0.0, 1.0 - (missing_count / max_missing)) if max_missing > 0 else 0.0
    return pref_sim * 0.7 + have_ratio * 0.2 + missing_penalty * 0.1


async def recommend_missing_ingredients(
    fridge_ingredients: list[str],
    preferences: dict,
    user_allergies: list[str],
    user_context: str,
    repo: RecipeRepository | None = None,
) -> list[dict]:
    """SDD §3.2 모델 B 추천 알고리즘."""
    # 빈 냉장고는 명시적 빈 응답 — 모든 레시피가 missing>0이 되어 의미 없는 추천 방지.
    if not fridge_ingredients:
        return []
    repo = repo or get_repository()
    fridge_norm_list = normalize_list(fridge_ingredients)
    fridge_norm = set(fridge_norm_list)
    # NFR-EVAL-001: 카테고리 알레르기를 세부재료로 확장 후 정규화.
    allergies = set(normalize_list(expand_allergies(user_allergies or [])))
    max_cook = int(preferences.get("max_cook_min", 60))
    max_missing = settings.missing_ingredients_max
    pref_vec = _vec_from_prefs(preferences)
    top_k_pre = settings.top_k_model_b_pre

    candidates: list[tuple[float, Recipe, list[str], list[str]]] = []
    for r in repo.list_all():
        # 2단계: 알레르기 + 조리시간
        if allergies and any(a in allergies for a in r.allergens):
            continue
        if r.cook_min > max_cook:
            continue
        # 3단계: 보유/부족 분류
        have, missing = _analyze_ingredients(fridge_norm, r.whole_ingredients)
        # 4단계: 소프트 필터
        # SDD §3.2 model_b 정의 — "부족 재료 N개만 더 사면 만들 수 있는" 레시피.
        # missing=0은 model_a(냉털) 영역이므로 model_b에서 명시적으로 제외 (중복 차단).
        if len(missing) == 0:
            continue
        if len(missing) > max_missing:
            continue
        if len(r.whole_ingredients) == 0:
            continue
        # 5단계: 복합 점수
        have_ratio = len(have) / len(r.whole_ingredients)
        pref_sim = _cosine(pref_vec, _vec_from_recipe(r, preferences))
        score = _composite_score(pref_sim, have_ratio, len(missing), max_missing)
        candidates.append((score, r, have, missing))

    # 6-pre: 상위 10개 사전 선별
    candidates.sort(key=lambda x: (-x[0], x[1].cook_min))
    pre = candidates[:top_k_pre]

    # 6-Gemini: 3개 선별 + 한국어 이유
    pre_payload = [
        {
            **r.to_brief_dict(),
            "final_score": round(float(score), 4),
            "have": have,
            "missing": missing,
        }
        for score, r, have, missing in pre
    ]
    whitelist = repo.whitelist_ids()
    gemini_result = await gemini_select_top3(pre_payload, user_context=user_context)

    # 7단계: citation_id 화이트리스트 검증 (NFR-EVAL-002)
    selected_ids: list[str] = []
    reasons_by_id: dict[str, str] = {}
    if gemini_result and gemini_result.get("selected"):
        sel = gemini_result["selected"]
        reasons = gemini_result.get("reasons", [])
        # NFR-EVAL-002 — citation_ids 누락/빈 리스트면 검증 실패로 처리.
        # (이전 자기 인용 폴백은 환각 차단 무력화)
        cites = gemini_result.get("citation_ids") or []
        if cites:
            for idx, rid in enumerate(sel):
                if rid in whitelist and rid in cites:
                    selected_ids.append(rid)
                    if idx < len(reasons):
                        reasons_by_id[rid] = reasons[idx]
                if len(selected_ids) >= settings.top_k_model_b_final:
                    break

    # 폴백: Gemini 실패 또는 검증 실패 시 final_score Top-3, 이유 빈 문자열
    if len(selected_ids) < settings.top_k_model_b_final:
        for entry in pre_payload:
            if entry["recipe_id"] not in selected_ids:
                selected_ids.append(entry["recipe_id"])
            if len(selected_ids) >= settings.top_k_model_b_final:
                break

    id_to_payload = {p["recipe_id"]: p for p in pre_payload}
    out: list[dict] = []
    for rid in selected_ids[: settings.top_k_model_b_final]:
        payload = id_to_payload.get(rid)
        if not payload:
            continue
        out.append({**payload, "reason": reasons_by_id.get(rid, "")})
    return out
