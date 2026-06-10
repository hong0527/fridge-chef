"""의미 임베딩 백엔드 · 하이브리드 결합 · NL retrieval 주입 회귀 테스트.

e5 모델 없이(설치/다운로드 불필요) 동작을 검증하기 위해 score_query 를 monkeypatch 한다.
"""

from __future__ import annotations

import pytest

from app.models.recipe import Recipe
from app.models.recipe_repository import RecipeRepository
from app.services import embedding_service as emb
from app.services import model_a as ma


# ──────────────────────── _combine_scores (하이브리드) ────────────────────────
class TestCombineScores:
    def test_max_of_normalized(self):
        tf = {"a": 0.10, "b": 0.00}
        sm = {"a": 0.00, "b": 0.90}
        out = emb._combine_scores(tf, sm)
        # 각자 min-max 정규화(tf: a=1,b=0 / sm: a=0,b=1) 후 per-recipe max → 둘 다 1.0
        assert out["a"] == pytest.approx(1.0)
        assert out["b"] == pytest.approx(1.0)

    def test_empty_semantic_returns_tfidf(self):
        tf = {"a": 0.3}
        assert emb._combine_scores(tf, {}) == tf

    def test_empty_tfidf_returns_semantic(self):
        sm = {"a": 0.8}
        assert emb._combine_scores({}, sm) == sm


# ──────────────────────── backend 라우팅 ────────────────────────
class TestBackendRouting:
    def test_set_backend_override(self):
        emb.set_backend("hybrid")
        assert emb._active_backend() == "hybrid"
        emb.set_backend(None)  # 복원

    def test_semantic_unready_falls_back_to_tfidf(self, monkeypatch):
        """의미 백엔드인데 캐시/모델 미준비 → TF-IDF 경로로 폴백 (빈 vectorizer면 {})."""
        emb.set_backend("semantic")
        monkeypatch.setattr(emb, "_VECTORIZER", None)
        monkeypatch.setattr(emb, "_MATRIX", None)
        from app.services import semantic_embedding_service as sem
        monkeypatch.setattr(sem, "is_ready", lambda: False)
        assert emb.score_query("비 오는 날") == {}
        emb.set_backend(None)


# ──────────────────────── NL retrieval 주입 (model_a) ────────────────────────
def _mk(rid, name, ings, *, country="kr", theme="main", spicy=1, diff=1, cook=20, allergens=None):
    return Recipe(
        recipe_id=rid, name=name, whole_ingredients=ings, cook_min=cook, spicy=spicy,
        difficulty_level=diff, is_low_calorie=False, country=country, theme=theme,
        allergens=allergens or [],
    )


@pytest.fixture
def _no_gemini(monkeypatch):
    async def _none(candidates, user_context):
        return None
    from app.services import gemini_client
    monkeypatch.setattr(gemini_client, "gemini_reasons_for_model_a", _none)


class TestNlRetrievalInjection:
    @pytest.mark.asyncio
    async def test_nl_injection_respects_makeable_only(self, monkeypatch, _no_gemini):
        """strict-A: NL 주입이 NL 점수가 아무리 높아도 '재료 부족(missing>0)' 후보를
        Model A(재료 완비만)에 노출하지 않는다. 완비 후보만 떠야 한다 (A·B 분리 보장)."""
        # INC: 재료 부족(소고기·버터 없음) but NL 최고점 → A에 뜨면 안 됨(B 영역)
        incomplete = _mk("INC", "기념일스테이크", ["밥", "소고기", "버터"], country="kr", theme="main")
        # CMP: 재료 완비(밥·계란만) → A에 떠야 함
        complete = _mk("CMP", "계란밥", ["밥", "계란"], country="kr", theme="main")
        repo = RecipeRepository([incomplete, complete])

        def fake_score(query_text, nl_text=""):
            return {"INC": 0.99, "CMP": 0.5}  # 부족한 INC에 최고 NL 점수
        monkeypatch.setattr(emb, "score_query", fake_score)
        ma.set_nl_retrieval_k(10)
        try:
            out = await ma.recommend_cold_storage(
                fridge_ingredients=["밥", "계란"],
                preferences={"country": "한식", "food_type": "메인요리", "spicy": 1,
                             "difficulty": "초보", "max_cook_min": 60},
                user_allergies=[], repo=repo, user_context="기념일에 근사하게 구운 고기",
            )
        finally:
            ma.set_nl_retrieval_k(None)
        ids = {r["recipe_id"] for r in out}
        assert "INC" not in ids, "재료 부족 후보가 Model A(완비)에 노출됨 — A·B 분리 위반"
        assert "CMP" in ids, "재료 완비 후보가 누락됨"

    @pytest.mark.asyncio
    async def test_injection_never_bypasses_allergy_or_country(self, monkeypatch, _no_gemini):
        """retrieval 주입도 알레르기·국가 hard filter 는 절대 우회하지 않는다 (안전 회귀)."""
        peanut = _mk("P", "땅콩요리", ["땅콩"], country="kr", theme="main", allergens=["땅콩"])
        western = _mk("W", "양식파스타", ["면"], country="west", theme="main")
        filler = [_mk(f"F{i}", f"밥{i}", ["밥", "계란"], country="kr", theme="main") for i in range(2)]
        repo = RecipeRepository([peanut, western, *filler])

        def fake_score(query_text, nl_text=""):
            return {"P": 0.99, "W": 0.99, "F0": 0.5, "F1": 0.5}  # 금지 대상에 최고점
        monkeypatch.setattr(emb, "score_query", fake_score)
        ma.set_nl_retrieval_k(10)
        try:
            out = await ma.recommend_cold_storage(
                fridge_ingredients=["밥", "계란"],
                preferences={"country": "한식", "food_type": "메인요리", "spicy": 1,
                             "difficulty": "초보", "max_cook_min": 60},
                user_allergies=["땅콩"], repo=repo, user_context="아무거나",
            )
        finally:
            ma.set_nl_retrieval_k(None)
        ids = {r["recipe_id"] for r in out}
        assert "P" not in ids, "알레르기(땅콩) 레시피가 NL 주입으로 노출됨 — NFR-EVAL-001 위반"
        assert "W" not in ids, "국가 불일치(양식) 레시피가 NL 주입으로 노출됨"
