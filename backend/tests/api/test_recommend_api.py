"""추천 API 통합 테스트 — SRS FR-011·014·016, NFR-PERF-002·003, NFR-REL-001, NFR-EVAL-001·002.

- FR-011 모델 A 냉털 추천 (≤ 3s)
- FR-014 모델 B 부족재료 추천 (≤ 10s)
- FR-016 Gemini 추천 이유 (8s 폴백)
- FR-007 알레르기 토글 (use_saved_allergies)
- NFR-EVAL-001: 알레르기 노출 0%
- NFR-EVAL-002: citation_id 화이트리스트 ≥ 95%
- NFR-REL-001: Gemini 실패 시 final_score 폴백 (reason="")
"""

from __future__ import annotations

import time

import pytest


# ─────────────────────────────────────────────────────────────
class TestRecommendBasic:
    """기본 동작 — 응답 구조 검증."""

    async def test_recommend_returns_dual_response(
        self, async_client, mock_gemini_success
    ) -> None:
        """# FR-011·014 — 정상 요청 → 200 + {model_a, model_b}."""
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘", "밥", "계란"],
            "preferences": {
                "spicy": 1,
                "difficulty": "초보",
                "diet": False,
                "use_saved_allergies": False,
                "food_type": "메인요리",
                "country": "한식",
                "max_cook_min": 60,
                "user_context": "",
            },
        }
        resp = await async_client.post("/api/recommend", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert "model_a" in body
        assert "model_b" in body
        assert isinstance(body["model_a"], list)
        assert isinstance(body["model_b"], list)
        # FR-011: 모델 A 최대 10개
        assert len(body["model_a"]) <= 10
        # FR-014: 모델 B 정확히 3개 (또는 후보 부족 시 0~3)
        assert len(body["model_b"]) <= 3

    async def test_recommend_empty_fridge_returns_200(
        self, async_client, mock_gemini_success
    ) -> None:
        """# FR-011 — 빈 냉장고 → 200 (모델 A 결과 0건 가능)."""
        payload = {"fridge_ingredients": [], "preferences": {}}
        resp = await async_client.post("/api/recommend", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        # contains_all 하드필터로 모델 A는 빈 결과 기대 (재료 없음)
        assert body["model_a"] == []

    async def test_recommend_model_a_schema_fields(
        self, async_client, mock_gemini_success
    ) -> None:
        """# FR-011 — 모델 A 응답 필드 검증 (recipe_id, name, score, ...)."""
        payload = {"fridge_ingredients": ["두부", "간장", "마늘"], "preferences": {}}
        resp = await async_client.post("/api/recommend", json=payload)
        body = resp.json()
        if body["model_a"]:
            item = body["model_a"][0]
            assert {"recipe_id", "name", "cook_min", "spicy", "difficulty_level",
                    "country", "theme", "score"} <= set(item.keys())

    async def test_recommend_model_b_includes_have_missing_reason(
        self, async_client, mock_gemini_success
    ) -> None:
        """# FR-014·016 — 모델 B 응답에 have/missing/reason 포함."""
        payload = {
            "fridge_ingredients": ["두부", "간장"],
            "preferences": {"max_cook_min": 60},
        }
        resp = await async_client.post("/api/recommend", json=payload)
        body = resp.json()
        for item in body["model_b"]:
            assert {"have", "missing", "reason", "final_score"} <= set(item.keys())


# ─────────────────────────────────────────────────────────────
class TestAllergyToggle:
    """FR-007 — 저장 알레르기 자동 적용 토글."""

    async def test_toggle_on_applies_saved_allergies(
        self, async_client, mock_gemini_success
    ) -> None:
        """# FR-007 — 토글 ON + X-User-Allergies 헤더 → 저장 알레르기 자동 적용."""
        payload = {
            "fridge_ingredients": ["밥", "계란", "간장", "두부", "마늘"],
            "preferences": {"use_saved_allergies": True, "max_cook_min": 60},
        }
        # 알레르기를 헤더로 주입 (get_current_user 스텁 파라미터)
        resp = await async_client.post(
            "/api/recommend",
            json=payload,
            headers={"X-User-Allergies": "계란"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # 계란 알레르기 → 계란 함유 레시피 제외 (r001 계란말이, r013 순두부찌개 등)
        for item in body["model_a"] + body["model_b"]:
            assert item["recipe_id"] not in {"r001", "r013", "r020"}, (
                "토글 ON: 알레르기 자동 적용 실패"
            )

    async def test_toggle_off_ignores_saved_allergies(
        self, async_client, mock_gemini_success
    ) -> None:
        """# FR-007 — 토글 OFF → 저장 알레르기 미적용 (결과 비교)."""
        payload_off = {
            "fridge_ingredients": ["밥", "계란", "간장"],
            "preferences": {"use_saved_allergies": False, "max_cook_min": 60},
        }
        resp_off = await async_client.post(
            "/api/recommend",
            json=payload_off,
            headers={"X-User-Allergies": "계란"},
        )
        body_off = resp_off.json()

        payload_on = {**payload_off, "preferences": {**payload_off["preferences"],
                                                     "use_saved_allergies": True}}
        resp_on = await async_client.post(
            "/api/recommend",
            json=payload_on,
            headers={"X-User-Allergies": "계란"},
        )
        body_on = resp_on.json()

        # OFF 결과에 계란 포함 레시피가 등장 가능, ON 결과에는 등장 불가
        ids_off = {r["recipe_id"] for r in body_off["model_a"]}
        ids_on = {r["recipe_id"] for r in body_on["model_a"]}
        # OFF 가 더 많은 후보를 가질 수 있음 (계란 함유 레시피 포함)
        assert len(ids_off) >= len(ids_on), "토글 OFF 시 후보가 더 많아야 함"


# ─────────────────────────────────────────────────────────────
class TestAllergyZeroExposure:
    """NFR-EVAL-001 — 알레르기 노출 0% (게이팅 기준)."""

    async def test_no_allergen_in_response_when_allergy_specified(
        self, async_client, mock_gemini_success
    ) -> None:
        """# NFR-EVAL-001 — 응답 어디에도 알레르기 재료 포함 0건."""
        from app.models.recipe_repository import get_repository

        repo = get_repository()
        payload = {
            "fridge_ingredients": ["밥", "계란", "두부", "간장", "마늘", "대파"],
            "preferences": {"use_saved_allergies": True, "max_cook_min": 60},
        }
        resp = await async_client.post(
            "/api/recommend",
            json=payload,
            headers={"X-User-Allergies": "계란,대두"},
        )
        body = resp.json()
        forbidden = {"계란", "대두"}
        for item in body["model_a"] + body["model_b"]:
            rec = repo.get(item["recipe_id"])
            assert rec is not None, f"recipe_id {item['recipe_id']} 화이트리스트 외"
            assert not (set(rec.allergens) & forbidden), (
                f"알레르기 노출: {item['recipe_id']} allergens={rec.allergens}"
            )


# ─────────────────────────────────────────────────────────────
class TestCitationWhitelist:
    """NFR-EVAL-002 — citation_id 화이트리스트 검증."""

    async def test_all_citation_ids_are_in_whitelist(
        self, async_client, mock_gemini_success
    ) -> None:
        """# NFR-EVAL-002 — 모든 model_b.recipe_id ∈ candidate whitelist."""
        from app.models.recipe_repository import get_repository

        repo = get_repository()
        whitelist = repo.whitelist_ids()
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘"],
            "preferences": {"max_cook_min": 60},
        }
        resp = await async_client.post("/api/recommend", json=payload)
        body = resp.json()
        for item in body["model_b"]:
            assert item["recipe_id"] in whitelist, (
                f"화이트리스트 외 ID 응답: {item['recipe_id']}"
            )

    async def test_hallucinated_citation_replaced_by_fallback(
        self, async_client, monkeypatch
    ) -> None:
        """# NFR-EVAL-002 — Gemini 가짜 ID → 화이트리스트 검증 + final_score 폴백."""
        from app.services import model_b as mb_mod

        async def _bad_gemini(candidates, user_context):
            return {
                "selected": ["fake_a", "fake_b", "fake_c"],
                "reasons": ["가짜1", "가짜2", "가짜3"],
                "citation_ids": ["fake_a", "fake_b", "fake_c"],
            }

        monkeypatch.setattr(mb_mod, "gemini_select_top3", _bad_gemini)
        from app.models.recipe_repository import get_repository

        whitelist = get_repository().whitelist_ids()
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘"],
            "preferences": {"max_cook_min": 60},
        }
        resp = await async_client.post("/api/recommend", json=payload)
        body = resp.json()
        for item in body["model_b"]:
            assert item["recipe_id"] in whitelist


# ─────────────────────────────────────────────────────────────
class TestPerformance:
    """NFR-PERF — 응답 시간 한도."""

    async def test_recommend_under_10s_NFR_PERF_003(
        self, async_client, mock_gemini_success
    ) -> None:
        """# NFR-PERF-003 — 전체 추천 응답 ≤ 10s."""
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘", "밥", "계란"],
            "preferences": {"max_cook_min": 60},
        }
        start = time.perf_counter()
        resp = await async_client.post("/api/recommend", json=payload)
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed <= 10.0, f"NFR-PERF-003 위반: {elapsed:.2f}s"

    async def test_model_a_under_3s_NFR_PERF_002(
        self, async_client, mock_gemini_fail
    ) -> None:
        """# NFR-PERF-002 — 모델 A (냉털) ≤ 3s.

        Gemini 폴백 모킹 → 모델 B 도 빠르게 종료 → 측정 가능.
        """
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘"],
            "preferences": {"max_cook_min": 60},
        }
        start = time.perf_counter()
        resp = await async_client.post("/api/recommend", json=payload)
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        # 듀얼 호출 + 폴백 → 3s 내 충분
        assert elapsed <= 3.0, f"NFR-PERF-002 위반: {elapsed:.2f}s"


# ─────────────────────────────────────────────────────────────
class TestGeminiFallback:
    """NFR-REL-001 — Gemini 8s 폴백."""

    async def test_gemini_failure_returns_empty_reason(
        self, async_client, mock_gemini_fail
    ) -> None:
        """# NFR-REL-001·FR-016 — Gemini 실패 시 final_score Top-3 + reason=""."""
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘"],
            "preferences": {"max_cook_min": 60},
        }
        resp = await async_client.post("/api/recommend", json=payload)
        body = resp.json()
        assert len(body["model_b"]) >= 1, "폴백이라도 결과 1건 이상"
        for item in body["model_b"]:
            assert item["reason"] == "", "폴백: reason 은 빈 문자열"
            assert "final_score" in item

    async def test_gemini_timeout_returns_fallback(
        self, async_client, monkeypatch
    ) -> None:
        """# NFR-REL-001 — Gemini 타임아웃 시뮬레이션."""
        import asyncio

        from app.services import model_b as mb_mod

        async def _slow_gemini(candidates, user_context):
            await asyncio.sleep(0.01)  # 빠른 모킹: 실제 SDK 의 8s 타임아웃을 미리 시뮬레이트
            return None  # 타임아웃 가정 → None

        monkeypatch.setattr(mb_mod, "gemini_select_top3", _slow_gemini)
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘"],
            "preferences": {"max_cook_min": 60},
        }
        resp = await async_client.post("/api/recommend", json=payload)
        assert resp.status_code == 200
        for item in resp.json()["model_b"]:
            assert item["reason"] == ""
