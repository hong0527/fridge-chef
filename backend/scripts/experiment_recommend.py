"""추천 시스템 실측 검증 — 6개 결함 수정 후 model A/B 동작 검증.

7개 실험으로 model A/B가 실제로 다른 기준으로 다른 결과를 내는지,
사용자 선호 변경에 따라 순위가 바뀌는지, 알레르기 차단이 작동하는지 검증.

실행: cd backend && python scripts/experiment_recommend.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# PYTHONPATH 보정
_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))

# 테스트 전용 환경변수 (security 부팅 가드용)
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-padding-1234567890")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("GEMINI_API_KEY", "")  # Gemini는 빈 키 → 폴백 강제

# noqa 무시
from app.models.recipe_repository import get_repository  # noqa: E402
from app.services import model_b as mb_mod  # noqa: E402
from app.services.model_a import recommend_cold_storage  # noqa: E402
from app.services.model_b import recommend_missing_ingredients  # noqa: E402
from app.services.recommend_service import recommend_dual  # noqa: E402

repo = get_repository()


# Gemini를 mock 처리 (None 반환 — 폴백 경로)
async def _mock_gemini_none(candidates, user_context):
    return None


async def _mock_gemini_ok(candidates, user_context):
    ids = [c["recipe_id"] for c in candidates[:3]]
    return {
        "selected": ids,
        "reasons": [f"{rid} mock 추천 이유" for rid in ids],
        "citation_ids": ids,
    }


def hline(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def fmt_recipe_row(d: dict, score_key: str = "score") -> str:
    rid = d.get("recipe_id", "?")
    name = d.get("name", "")
    country = d.get("country", "")
    theme = d.get("theme", "")
    cook = d.get("cook_min", "?")
    score = d.get(score_key, 0)
    have = d.get("have", None)
    missing = d.get("missing", None)
    reason = d.get("reason", "")
    base = f"  {rid:5s} {name:12s} {country:5s} {theme:8s} cook={cook:3d} {score_key}={score:.4f}"
    if have is not None:
        base += f" have={have} missing={missing}"
    if reason:
        base += f" reason={reason[:30]}"
    return base


async def experiment_1() -> None:
    """실험 1: 동일 입력에 model A vs model B 결과 차이."""
    hline("실험 1 — 동일 입력에 model A vs model B 결과 차이 (Gemini mock_ok)")
    mb_mod.gemini_select_top3 = _mock_gemini_ok

    fridge = ["양파", "마늘", "계란", "김치", "돼지고기", "두부", "대파", "밥", "고추장"]
    prefs = {
        "spicy": 3,
        "country": "한식",
        "food_type": "메인요리",
        "difficulty": "초보",
        "max_cook_min": 60,
        "diet": False,
    }
    a = await recommend_cold_storage(fridge, prefs, [], repo=repo)
    b = await recommend_missing_ingredients(fridge, prefs, [], "맛있는 한끼", repo=repo)

    print(f"\nModel A (냉털, score 코사인) — {len(a)}건:")
    for r in a:
        print(fmt_recipe_row(r, "score"))

    print(f"\nModel B (부족재료, final_score 복합) — {len(b)}건:")
    for r in b:
        print(fmt_recipe_row(r, "final_score"))

    a_ids = {r["recipe_id"] for r in a}
    b_ids = {r["recipe_id"] for r in b}
    overlap = a_ids & b_ids
    print(f"\n[비교] A 결과: {len(a_ids)}건  B 결과: {len(b_ids)}건  겹침: {len(overlap)}건 = {sorted(overlap) or '없음'}")
    print(f"[비교] A 전용: {sorted(a_ids - b_ids)}  B 전용: {sorted(b_ids - a_ids)}")


async def experiment_2() -> None:
    """실험 2: 사용자 선호 country 변경 시 model_a Top-5 순위 변화."""
    hline("실험 2 — country 5종 변경에 따른 model_a Top-5 변화 (Phase 4 동치 매칭 효과)")
    mb_mod.gemini_select_top3 = _mock_gemini_none

    fridge = ["양파", "마늘", "계란", "김치", "돼지고기", "두부", "대파", "밥",
              "면", "토마토", "올리브유", "치즈", "닭고기", "당근", "감자",
              "어묵", "고추장", "버섯", "쌀", "김"]  # 풍부
    base_prefs = {
        "spicy": 2, "food_type": "메인요리", "difficulty": "초보",
        "max_cook_min": 60, "diet": False,
    }
    for country in ["한식", "중식", "일식", "양식", "기타"]:
        prefs = {**base_prefs, "country": country}
        a = await recommend_cold_storage(fridge, prefs, [], repo=repo)
        top5 = a[:5]
        ids_countries = [(r["recipe_id"], r.get("country", "?"), r["score"]) for r in top5]
        print(f"\nprefs.country={country} → Top-5:")
        for rid, c, s in ids_countries:
            print(f"  {rid}  country={c}  score={s:.4f}")


async def experiment_3() -> None:
    """실험 3: 알레르기 카테고리 차단 (NFR-EVAL-001)."""
    hline("실험 3 — 알레르기 차단 (세부 vs 카테고리, NFR-EVAL-001)")
    mb_mod.gemini_select_top3 = _mock_gemini_none

    fridge = ["계란", "대파", "소금", "두부", "마늘", "치즈", "면",
              "양파", "당근", "올리브유", "토마토", "밥"]
    prefs = {"spicy": 2, "country": "한식", "food_type": "메인요리",
             "difficulty": "초보", "max_cook_min": 60, "diet": False}

    # 시드의 allergens 매트릭스 표시용
    print("\n[참고] 시드 35건 중 주요 알레르겐 보유:")
    egg_recipes = [r.recipe_id for r in repo.list_all() if "계란" in r.allergens]
    milk_recipes = [r.recipe_id for r in repo.list_all() if "우유" in r.allergens]
    soy_recipes = [r.recipe_id for r in repo.list_all() if "대두" in r.allergens]
    print(f"  계란 함유: {egg_recipes}")
    print(f"  우유 함유: {milk_recipes}")
    print(f"  대두 함유: {soy_recipes}")

    for case_name, allergies, forbidden in [
        ("baseline (알레르기 없음)", [], set()),
        ("세부 키워드: 계란", ["계란"], {"계란"}),
        ("카테고리: 난류 (NFR-EVAL-001 핵심)", ["난류"], {"계란"}),  # 난류→계란/달걀 확장
        ("카테고리: 우유 (확장)", ["우유"], {"우유"}),  # 우유→치즈/버터/크림 확장
        ("카테고리: 대두", ["대두"], {"대두"}),
    ]:
        a = await recommend_cold_storage(fridge, prefs, allergies, repo=repo)
        b = await recommend_missing_ingredients(fridge, prefs, allergies, "", repo=repo)
        rids = [r["recipe_id"] for r in a + b]
        # 노출 검증
        leaked = []
        for rid in rids:
            rec = repo.get(rid)
            if rec and (set(rec.allergens) & forbidden):
                leaked.append((rid, rec.allergens))
        verdict = "✅ 차단 OK" if not leaked or not forbidden else "❌ 노출 발생"
        if not forbidden:
            verdict = "— (baseline)"
        print(f"\n[{case_name}] A:{len(a)}건  B:{len(b)}건  {verdict}")
        if leaked:
            print(f"  누출: {leaked}")
        print(f"  A 결과: {[r['recipe_id'] for r in a][:5]}{'...' if len(a) > 5 else ''}")
        print(f"  B 결과: {[r['recipe_id'] for r in b]}")


async def experiment_4() -> None:
    """실험 4: model_b missing 의미 검증 — 양념 제외됐는지."""
    hline("실험 4 — model_b missing 의미 (양념 제외 검증)")
    mb_mod.gemini_select_top3 = _mock_gemini_none

    fridge = ["계란", "대파"]  # 적게 — missing이 풍부하게 나옴
    prefs = {"spicy": 2, "country": "한식", "food_type": "메인요리",
             "difficulty": "초보", "max_cook_min": 60, "diet": False}
    b = await recommend_missing_ingredients(fridge, prefs, [], "", repo=repo)
    print(f"\n냉장고: {fridge}  → model_b {len(b)}건:")
    for r in b:
        print(f"  {r['recipe_id']} {r['name']:12s} have={r['have']}  missing={r['missing']}")
    # 양념(소금/식용유)이 missing에 들어있는지 확인
    BASIC_SEASONINGS = {"소금", "설탕", "물", "후추", "식용유", "올리브유",
                       "참기름", "들기름", "간장", "고추장", "된장"}
    has_seasoning_in_missing = any(
        ing in BASIC_SEASONINGS for r in b for ing in r["missing"]
    )
    print(f"\n[검증] missing 필드에 양념 포함: {'❌ YES (Phase 3 결함)' if has_seasoning_in_missing else '✅ NO (양념 정상 제외)'}")


async def experiment_5() -> None:
    """실험 5: 점수 분포 분석 (이전 평탄성 결함 해결 검증)."""
    hline("실험 5 — model_a score 분포 (Phase 4 동치 매칭 후)")
    mb_mod.gemini_select_top3 = _mock_gemini_none

    fridge = ["양파", "마늘", "계란", "김치", "돼지고기", "두부", "대파", "밥",
              "면", "올리브유", "치즈", "닭고기", "당근", "감자", "버섯"]
    prefs = {"spicy": 2, "country": "한식", "food_type": "메인요리",
             "difficulty": "초보", "max_cook_min": 60, "diet": False}
    a = await recommend_cold_storage(fridge, prefs, [], repo=repo)
    scores = [r["score"] for r in a]
    if scores:
        print(f"\nscore 분포 ({len(scores)}건):")
        print(f"  min={min(scores):.4f}  max={max(scores):.4f}  range={max(scores)-min(scores):.4f}")
        print(f"  unique scores={len(set(round(s, 4) for s in scores))}")
        # 분포 구간
        buckets = {">0.9": 0, "0.7-0.9": 0, "0.5-0.7": 0, "0.3-0.5": 0, "<=0.3": 0}
        for s in scores:
            if s > 0.9:
                buckets[">0.9"] += 1
            elif s > 0.7:
                buckets["0.7-0.9"] += 1
            elif s > 0.5:
                buckets["0.5-0.7"] += 1
            elif s > 0.3:
                buckets["0.3-0.5"] += 1
            else:
                buckets["<=0.3"] += 1
        print(f"  분포: {buckets}")
        # 이전(평탄성 결함): 95%가 0.7~1.0에 몰림
        # 수정 후 기대: 더 넓게 분산
        flat_ratio = (buckets[">0.9"] + buckets["0.7-0.9"]) / len(scores)
        print(f"  0.7+ 비율: {flat_ratio*100:.0f}% (이전 ~95% → 수정 후 감소 기대)")


async def experiment_6() -> None:
    """실험 6: 빈 냉장고/빈 알레르기 안전성."""
    hline("실험 6 — 엣지 케이스 안전성")
    mb_mod.gemini_select_top3 = _mock_gemini_none

    cases = [
        ("빈 냉장고", [], [], {}),
        ("빈 알레르기 + 풍부한 냉장고", ["계란", "대파", "소금", "두부", "마늘"], [], {}),
        ("max_cook_min=5 (매우 짧음)", ["계란", "대파", "소금"], [], {"max_cook_min": 5}),
    ]
    base_prefs = {"spicy": 2, "country": "한식", "food_type": "메인요리",
                  "difficulty": "초보", "max_cook_min": 60, "diet": False}
    for name, fridge, allergies, override in cases:
        prefs = {**base_prefs, **override}
        try:
            a = await recommend_cold_storage(fridge, prefs, allergies, repo=repo)
            b = await recommend_missing_ingredients(fridge, prefs, allergies, "", repo=repo)
            print(f"\n[{name}]")
            print(f"  A: {len(a)}건 {[r['recipe_id'] for r in a][:3]}")
            print(f"  B: {len(b)}건 {[r['recipe_id'] for r in b][:3]}")
        except Exception as e:
            print(f"\n[{name}] ❌ 예외 발생: {type(e).__name__}: {e}")


async def experiment_7() -> None:
    """실험 7: recommend_dual 통합 동작."""
    hline("실험 7 — recommend_dual 통합 (Phase 2 gather 분리 효과)")
    mb_mod.gemini_select_top3 = _mock_gemini_ok

    fridge = ["양파", "마늘", "계란", "김치", "돼지고기", "두부", "대파", "밥"]
    prefs = {"spicy": 2, "country": "한식", "food_type": "메인요리",
             "difficulty": "초보", "max_cook_min": 60, "diet": False}
    result = await recommend_dual(fridge, prefs, [], "맛있게", repo=repo)
    print(f"\n응답 키: {list(result.keys())}")
    print(f"model_a: {len(result['model_a'])}건 {[r['recipe_id'] for r in result['model_a']]}")
    print(f"model_b: {len(result['model_b'])}건 {[r['recipe_id'] for r in result['model_b']]}")
    print(f"\n[검증] Phase 2 gather 분리 — Gemini 정상 mock 시 두 모델 모두 응답: "
          f"{'✅' if result['model_a'] and result['model_b'] else '❌'}")

    # Gemini fail 케이스
    mb_mod.gemini_select_top3 = _mock_gemini_none
    result2 = await recommend_dual(fridge, prefs, [], "", repo=repo)
    print(f"\n[Gemini fail 시] model_a: {len(result2['model_a'])}건  model_b: {len(result2['model_b'])}건")
    print(f"[검증] Gemini fail에도 model_a 보존: "
          f"{'✅' if result2['model_a'] else '❌ (이전 결함 재발)'}")


async def main() -> None:
    await experiment_1()
    await experiment_2()
    await experiment_3()
    await experiment_4()
    await experiment_5()
    await experiment_6()
    await experiment_7()
    print("\n" + "=" * 78)
    print("실험 완료 — 위 결과를 분석에 활용하세요.")
    print("=" * 78)


if __name__ == "__main__":
    asyncio.run(main())
