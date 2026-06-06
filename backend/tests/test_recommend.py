"""추천 단위 테스트 (SRS NFR-EVAL-001 알레르기 0%, NFR-EVAL-002 인용 ≥95%).

- 50샘플 골든셋 placeholder 형식만 정의 (실 데이터는 별도 큐레이션 작업).
- Gemini 외부 호출은 monkeypatch 로 모킹 → 결정론 보장.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.synonym_map import normalize, normalize_list
from app.models.recipe import Recipe
from app.models.recipe_repository import RecipeRepository
from app.services import gemini_client as gc_mod
from app.services import model_b as mb_mod
from app.services.model_a import recommend_cold_storage
from app.services.model_b import recommend_missing_ingredients
from app.services.recommend_service import recommend_dual


def _make_repo() -> RecipeRepository:
    """결정론적 미니 카탈로그."""
    recipes = [
        Recipe("t001", "간장계란밥", normalize_list(["밥", "계란", "간장"]), cook_min=10,
               spicy=1, difficulty_level=1, country="kr", theme="main",
               allergens=normalize_list(["계란", "대두"])),
        Recipe("t002", "두부조림", normalize_list(["두부", "간장", "마늘"]), cook_min=20,
               spicy=2, difficulty_level=1, allergens=normalize_list(["대두"])),
        Recipe("t003", "닭가슴살구이", normalize_list(["닭가슴살", "올리브유"]), cook_min=15,
               spicy=1, difficulty_level=1, is_low_calorie=True, country="west",
               allergens=normalize_list(["닭고기"])),
        Recipe("t004", "파스타", normalize_list(["면", "치즈", "마늘"]), cook_min=25,
               spicy=1, difficulty_level=2, country="west", allergens=normalize_list(["밀", "우유"])),
        Recipe("t005", "야채볶음", normalize_list(["양파", "버섯", "당근"]), cook_min=15,
               spicy=1, difficulty_level=1, is_low_calorie=True, theme="side"),
    ]
    return RecipeRepository(recipes)


# -------------- 동의어 정규화 --------------


def test_synonym_normalizes_known_pairs() -> None:
    assert normalize("쪽파") == "대파"
    assert normalize("청양고추") == "고추"
    assert normalize("피자치즈") == "치즈"
    assert normalize("닭가슴살") == "닭고기"


def test_synonym_passthrough_unknown() -> None:
    assert normalize("당근") == "당근"
    assert normalize("두부") == "두부"


def test_normalize_list_dedupes_order_preserving() -> None:
    out = normalize_list(["쪽파", "대파", "양파"])
    assert out == ["대파", "양파"]


# -------------- 모델 A — 코사인 유사도 --------------


@pytest.mark.asyncio
async def test_model_a_hard_filter_contains_all() -> None:
    repo = _make_repo()
    # 냉장고에 두부+간장+마늘만 있음 → t002(두부조림)만 통과
    out = await recommend_cold_storage(
        fridge_ingredients=["두부", "간장", "마늘"],
        preferences={"spicy": 2, "difficulty": "초보", "max_cook_min": 60,
                     "country": "한식", "food_type": "메인요리"},
        user_allergies=[],
        repo=repo,
    )
    rids = [r["recipe_id"] for r in out]
    assert "t002" in rids
    # 다른 레시피는 재료 부족으로 제외
    assert "t001" not in rids


@pytest.mark.asyncio
async def test_model_a_allergy_zero_exposure() -> None:
    """NFR-EVAL-001 — 알레르기 노출 0%."""
    repo = _make_repo()
    out = await recommend_cold_storage(
        fridge_ingredients=["밥", "계란", "간장", "두부", "마늘"],
        preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                     "country": "한식", "food_type": "메인요리"},
        user_allergies=["계란"],  # 계란 알레르기
        repo=repo,
    )
    for r in out:
        assert "계란" not in [a for a in repo.get(r["recipe_id"]).allergens]


@pytest.mark.asyncio
async def test_model_a_max_cook_min_filter() -> None:
    repo = _make_repo()
    out = await recommend_cold_storage(
        fridge_ingredients=["두부", "간장", "마늘"],
        preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 15,
                     "country": "한식", "food_type": "메인요리"},
        user_allergies=[],
        repo=repo,
    )
    # t002 cook_min=20 > 15 → 제외
    assert all(r["recipe_id"] != "t002" for r in out)


# -------------- 모델 B — 복합 점수 + Gemini --------------


@pytest.mark.asyncio
async def test_model_b_uses_gemini_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _make_repo()

    async def _mock_gemini(candidates: list[dict], user_context: str) -> dict[str, Any]:
        ids = [c["recipe_id"] for c in candidates[:3]]
        return {
            "selected": ids,
            "reasons": [f"{rid} 추천 사유" for rid in ids],
            "citation_ids": ids,
        }

    monkeypatch.setattr(mb_mod, "gemini_select_top3", _mock_gemini)
    out = await recommend_missing_ingredients(
        fridge_ingredients=["두부", "간장"],
        preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                     "country": "한식", "food_type": "메인요리"},
        user_allergies=[],
        user_context="와인과 같이",
        repo=repo,
    )
    assert 1 <= len(out) <= 3
    for r in out:
        assert r["reason"].endswith("추천 사유")
        assert "have" in r and "missing" in r


@pytest.mark.asyncio
async def test_model_b_fallback_when_gemini_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _make_repo()

    async def _fail_gemini(candidates: list[dict], user_context: str) -> None:
        return None

    monkeypatch.setattr(mb_mod, "gemini_select_top3", _fail_gemini)
    out = await recommend_missing_ingredients(
        fridge_ingredients=["두부", "간장"],
        preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                     "country": "한식", "food_type": "메인요리"},
        user_allergies=[],
        user_context="",
        repo=repo,
    )
    # 폴백 동작: 결과 있고 reason 은 결정론 한국어 문장
    # (critic F3 빈 카드 차단 패치 — 이전 reason="" 가정 폐기).
    assert len(out) >= 1
    for r in out:
        assert r["reason"], "폴백이라도 결정론 reason 자동 생성"
        assert "보유" in r["reason"] or "활용" in r["reason"]


@pytest.mark.asyncio
async def test_model_b_citation_whitelist_drops_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-EVAL-002 — 화이트리스트에 없는 id는 폴백으로 대체."""
    repo = _make_repo()

    async def _bad_gemini(candidates: list[dict], user_context: str) -> dict[str, Any]:
        return {
            "selected": ["nonexistent_id_x", "nonexistent_id_y", "nonexistent_id_z"],
            "reasons": ["가짜1", "가짜2", "가짜3"],
            "citation_ids": ["nonexistent_id_x", "nonexistent_id_y", "nonexistent_id_z"],
        }

    monkeypatch.setattr(mb_mod, "gemini_select_top3", _bad_gemini)
    out = await recommend_missing_ingredients(
        fridge_ingredients=["두부", "간장"],
        preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                     "country": "한식", "food_type": "메인요리"},
        user_allergies=[],
        user_context="",
        repo=repo,
    )
    whitelist = repo.whitelist_ids()
    for r in out:
        assert r["recipe_id"] in whitelist  # 화이트리스트 검증 통과


# -------------- 동시 실행 --------------


@pytest.mark.asyncio
async def test_recommend_dual_concurrent(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _make_repo()

    async def _mock_gemini(candidates: list[dict], user_context: str) -> dict[str, Any]:
        ids = [c["recipe_id"] for c in candidates[:3]]
        return {"selected": ids, "reasons": ["x"] * len(ids), "citation_ids": ids}

    monkeypatch.setattr(mb_mod, "gemini_select_top3", _mock_gemini)

    result = await recommend_dual(
        fridge_ingredients=["두부", "간장", "마늘", "밥", "계란"],
        preferences={"spicy": 1, "difficulty": "초보", "max_cook_min": 60,
                     "country": "한식", "food_type": "메인요리"},
        user_allergies=[],
        user_context="",
        repo=repo,
    )
    assert "model_a" in result and "model_b" in result
    assert isinstance(result["model_a"], list)
    assert isinstance(result["model_b"], list)


# -------------- Gemini 응답 파서 --------------


def test_gemini_parser_handles_code_fence() -> None:
    raw = '```json\n{"selected":["a","b","c"],"reasons":["x","y","z"],"citation_ids":["a","b","c"]}\n```'
    parsed = gc_mod._parse_response_text(raw)
    assert parsed is not None
    assert parsed["selected"] == ["a", "b", "c"]


def test_gemini_parser_handles_plain_json() -> None:
    raw = '{"selected":["a"],"reasons":["x"],"citation_ids":["a"]}'
    parsed = gc_mod._parse_response_text(raw)
    assert parsed and parsed["selected"] == ["a"]


def test_gemini_parser_rejects_malformed() -> None:
    assert gc_mod._parse_response_text("not json at all") is None
    assert gc_mod._parse_response_text("") is None


# -------------- 50샘플 골든셋 placeholder --------------


GOLDEN_SAMPLES_50: list[dict[str, Any]] = [
    # TODO(curation): 알레르기 0% 검증용 50샘플.
    # 형식: {"fridge": [...], "preferences": {...}, "allergies": [...], "expect_zero": True}
    # 예시 placeholder 5개 — 실 데이터는 추후 추가
    {"fridge": ["밥", "계란"], "preferences": {"spicy": 1}, "allergies": ["계란"], "expect_zero": True},
    {"fridge": ["두부", "간장"], "preferences": {"spicy": 2}, "allergies": ["대두"], "expect_zero": True},
    {"fridge": ["면", "치즈"], "preferences": {"spicy": 1}, "allergies": ["밀"], "expect_zero": True},
    {"fridge": ["닭가슴살"], "preferences": {"spicy": 1}, "allergies": ["닭고기"], "expect_zero": True},
    {"fridge": ["새우", "마늘"], "preferences": {"spicy": 1}, "allergies": ["새우"], "expect_zero": True},
]


@pytest.mark.asyncio
async def test_golden_set_allergy_zero_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-EVAL-001 골든셋 회귀 — 알레르기 노출 0% 보장.

    50샘플 placeholder 의 일부(5개)로 회귀 가드. 큐레이션 완료 후 50으로 확장.
    """
    repo = _make_repo()

    async def _noop_gemini(candidates: list[dict], user_context: str) -> None:
        return None

    monkeypatch.setattr(mb_mod, "gemini_select_top3", _noop_gemini)

    for sample in GOLDEN_SAMPLES_50:
        prefs = {
            "spicy": sample["preferences"].get("spicy", 1),
            "difficulty": "초보",
            "max_cook_min": 60,
            "country": "한식",
            "food_type": "메인요리",
        }
        result = await recommend_dual(
            fridge_ingredients=sample["fridge"],
            preferences=prefs,
            user_allergies=sample["allergies"],
            user_context="",
            repo=repo,
        )
        forbidden = set(normalize_list(sample["allergies"]))
        for r in result["model_a"] + result["model_b"]:
            rec = repo.get(r["recipe_id"])
            assert rec is not None
            assert not (set(rec.allergens) & forbidden), (
                f"알레르기 노출 발견: {r['recipe_id']} allergens={rec.allergens} blocked={forbidden}"
            )
