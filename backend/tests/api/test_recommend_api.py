"""추천 API 통합 테스트 — SRS FR-011·014·016, NFR-PERF-002·003, NFR-REL-001, NFR-EVAL-001·002.

- FR-011 모델 A 냉털 추천 (≤ 3s)
- FR-014 모델 B 부족재료 추천 (≤ 10s)
- FR-016 Gemini 추천 이유 (8s 폴백)
- FR-007 알레르기 토글 (use_saved_allergies)
- NFR-EVAL-001: 알레르기 노출 0%
- NFR-EVAL-002: citation_id 화이트리스트 ≥ 95%
- NFR-REL-001: Gemini 실패 시 final_score 폴백 (reason="")

NOTE: 모든 인증 라우터는 JWT Bearer 필수. test_jwt_token fixture 의 헤더를 사용한다.
"""

from __future__ import annotations

import time


async def _set_user_allergies(
    async_client, test_jwt_token, allergies: list[str]
) -> None:
    """저장 알레르기를 PATCH 대용 — fridge 라우터로 가입 후 DB row 직접 갱신 대신
    가입 시점에 allergies 주입한 user 를 재가입해서 헤더를 받는 방식이 가장 격리적.
    여기서는 conftest test_user/test_jwt_token 을 재사용하지 않고 별도 user 를 만든다.
    """
    # 이 헬퍼는 사용하지 않는다 — 각 테스트가 직접 별도 user 가입을 수행한다.
    raise NotImplementedError


async def _signup_user_with_allergies(
    async_client, email: str, allergies: list[str]
) -> dict[str, str]:
    """별도 user 가입 + 로그인 → Bearer 헤더 반환."""
    await async_client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "Test1234!",
            "nickname": "tester-allergy",
            "allergies": allergies,
        },
    )
    login = await async_client.post(
        "/api/auth/login",
        json={"email": email, "password": "Test1234!"},
    )
    assert login.status_code == 200, f"login 실패: {login.text}"
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────
class TestRecommendBasic:
    """기본 동작 — 응답 구조 검증."""

    async def test_recommend_returns_dual_response(
        self, async_client, test_jwt_token, mock_gemini_success
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
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=test_jwt_token
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "model_a" in body
        assert "model_b" in body
        assert isinstance(body["model_a"], list)
        assert isinstance(body["model_b"], list)
        assert len(body["model_a"]) <= 10
        assert len(body["model_b"]) <= 3

    async def test_recommend_empty_fridge_returns_200(
        self, async_client, test_jwt_token, mock_gemini_success
    ) -> None:
        """# FR-011 — 빈 냉장고 → 200 (모델 A 결과 0건 가능)."""
        payload = {"fridge_ingredients": [], "preferences": {}}
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=test_jwt_token
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["model_a"] == []

    async def test_recommend_model_a_schema_fields(
        self, async_client, test_jwt_token, mock_gemini_success
    ) -> None:
        """# FR-011 — 모델 A 응답 필드 검증 (recipe_id, name, score, ...)."""
        payload = {"fridge_ingredients": ["두부", "간장", "마늘"], "preferences": {}}
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=test_jwt_token
        )
        body = resp.json()
        if body["model_a"]:
            item = body["model_a"][0]
            assert {
                "recipe_id", "name", "cook_min", "spicy", "difficulty_level",
                "country", "theme", "score",
            } <= set(item.keys())

    async def test_recommend_model_b_includes_have_missing_reason(
        self, async_client, test_jwt_token, mock_gemini_success
    ) -> None:
        """# FR-014·016 — 모델 B 응답에 have/missing/reason 포함."""
        payload = {
            "fridge_ingredients": ["두부", "간장"],
            "preferences": {"max_cook_min": 60},
        }
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=test_jwt_token
        )
        body = resp.json()
        for item in body["model_b"]:
            assert {"have", "missing", "reason", "final_score"} <= set(item.keys())


# ─────────────────────────────────────────────────────────────
class TestAllergyToggle:
    """FR-007 — 저장 알레르기 자동 적용 토글.

    NOTE: 이전 X-User-Allergies 헤더 방식은 폐기. 알레르기는 가입 시 user 에 저장되며,
    `preferences.use_saved_allergies` 토글로 적용 여부를 결정한다.
    """

    async def test_toggle_on_applies_saved_allergies(
        self, async_client, mock_gemini_success
    ) -> None:
        """# FR-007 — 토글 ON → 가입 시 저장된 알레르기 자동 적용."""
        headers = await _signup_user_with_allergies(
            async_client, "toggle-on@test.io", allergies=["계란"]
        )
        payload = {
            "fridge_ingredients": ["밥", "계란", "간장", "두부", "마늘"],
            "preferences": {"use_saved_allergies": True, "max_cook_min": 60},
        }
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=headers
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
        headers = await _signup_user_with_allergies(
            async_client, "toggle-off@test.io", allergies=["계란"]
        )
        payload_off = {
            "fridge_ingredients": ["밥", "계란", "간장"],
            "preferences": {"use_saved_allergies": False, "max_cook_min": 60},
        }
        resp_off = await async_client.post(
            "/api/recommend", json=payload_off, headers=headers
        )
        body_off = resp_off.json()

        payload_on = {
            **payload_off,
            "preferences": {**payload_off["preferences"], "use_saved_allergies": True},
        }
        resp_on = await async_client.post(
            "/api/recommend", json=payload_on, headers=headers
        )
        body_on = resp_on.json()

        ids_off = {r["recipe_id"] for r in body_off["model_a"]}
        ids_on = {r["recipe_id"] for r in body_on["model_a"]}
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
        headers = await _signup_user_with_allergies(
            async_client, "zero-exposure@test.io", allergies=["계란", "대두"]
        )
        payload = {
            "fridge_ingredients": ["밥", "계란", "두부", "간장", "마늘", "대파"],
            "preferences": {"use_saved_allergies": True, "max_cook_min": 60},
        }
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=headers
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
        self, async_client, test_jwt_token, mock_gemini_success
    ) -> None:
        """# NFR-EVAL-002 — 모든 model_b.recipe_id ∈ candidate whitelist."""
        from app.models.recipe_repository import get_repository

        repo = get_repository()
        whitelist = repo.whitelist_ids()
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘"],
            "preferences": {"max_cook_min": 60},
        }
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=test_jwt_token
        )
        body = resp.json()
        for item in body["model_b"]:
            assert item["recipe_id"] in whitelist, (
                f"화이트리스트 외 ID 응답: {item['recipe_id']}"
            )

    async def test_hallucinated_citation_replaced_by_fallback(
        self, async_client, test_jwt_token, monkeypatch
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
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=test_jwt_token
        )
        body = resp.json()
        for item in body["model_b"]:
            assert item["recipe_id"] in whitelist


# ─────────────────────────────────────────────────────────────
class TestPerformance:
    """NFR-PERF — 응답 시간 한도."""

    async def test_recommend_under_10s_NFR_PERF_003(
        self, async_client, test_jwt_token, mock_gemini_success
    ) -> None:
        """# NFR-PERF-003 — 전체 추천 응답 ≤ 10s."""
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘", "밥", "계란"],
            "preferences": {"max_cook_min": 60},
        }
        start = time.perf_counter()
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=test_jwt_token
        )
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed <= 10.0, f"NFR-PERF-003 위반: {elapsed:.2f}s"

    async def test_model_a_under_3s_NFR_PERF_002(
        self, async_client, test_jwt_token, mock_gemini_fail
    ) -> None:
        """# NFR-PERF-002 — 모델 A (냉털) ≤ 3s."""
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘"],
            "preferences": {"max_cook_min": 60},
        }
        start = time.perf_counter()
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=test_jwt_token
        )
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert elapsed <= 3.0, f"NFR-PERF-002 위반: {elapsed:.2f}s"


# ─────────────────────────────────────────────────────────────
class TestGeminiFallback:
    """NFR-REL-001 — Gemini 8s 폴백."""

    async def test_gemini_failure_returns_empty_reason(
        self, async_client, test_jwt_token, mock_gemini_fail
    ) -> None:
        """# NFR-REL-001·FR-016 — Gemini 실패 시 final_score Top-3 + reason=""."""
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘"],
            "preferences": {"max_cook_min": 60},
        }
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=test_jwt_token
        )
        body = resp.json()
        assert len(body["model_b"]) >= 1, "폴백이라도 결과 1건 이상"
        for item in body["model_b"]:
            assert item["reason"] == "", "폴백: reason 은 빈 문자열"
            assert "final_score" in item

    async def test_gemini_timeout_returns_fallback(
        self, async_client, test_jwt_token, monkeypatch
    ) -> None:
        """# NFR-REL-001 — Gemini 타임아웃 시뮬레이션."""
        import asyncio

        from app.services import model_b as mb_mod

        async def _slow_gemini(candidates, user_context):
            await asyncio.sleep(0.01)
            return None

        monkeypatch.setattr(mb_mod, "gemini_select_top3", _slow_gemini)
        payload = {
            "fridge_ingredients": ["두부", "간장", "마늘"],
            "preferences": {"max_cook_min": 60},
        }
        resp = await async_client.post(
            "/api/recommend", json=payload, headers=test_jwt_token
        )
        assert resp.status_code == 200
        for item in resp.json()["model_b"]:
            assert item["reason"] == ""
