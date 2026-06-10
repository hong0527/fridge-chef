"""냉장고 CRUD API 통합 테스트 — SRS FR-008~010, SDD §3.2.

- FR-008 재료 추가
- FR-009 재료 조회
- FR-010 재료 삭제
- SDD §3.2: 입력 즉시 SYNONYM_MAP 정규화 ("쪽파"→"대파")
- 모든 엔드포인트 JWT 인증 필수 (SDD §NFR-SEC: API 접근 제어)
"""

from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────
class TestFridgeAuth:
    """JWT 가드."""

    async def test_get_without_token_returns_401(self, async_client) -> None:
        """# JWT 인증 필수 — JWT 미포함 → 401."""
        resp = await async_client.get("/api/fridge")
        assert resp.status_code == 401

    async def test_post_without_token_returns_401(self, async_client) -> None:
        """# JWT 인증 필수 — POST 토큰 미포함 → 401."""
        resp = await async_client.post("/api/fridge", json={"raw_name": "두부"})
        assert resp.status_code == 401

    async def test_delete_without_token_returns_401(self, async_client) -> None:
        """# JWT 인증 필수 — DELETE 토큰 미포함 → 401."""
        resp = await async_client.delete("/api/fridge/1")
        assert resp.status_code == 401

    async def test_malformed_authorization_header_returns_401(self, async_client) -> None:
        """# JWT 인증 필수 — Bearer prefix 누락 → 401."""
        resp = await async_client.get(
            "/api/fridge", headers={"Authorization": "InvalidToken"}
        )
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────
class TestFridgeCRUD:
    """POST/GET/DELETE /api/fridge — FR-008~010."""

    async def test_create_ingredient_returns_201(self, async_client, test_jwt_token) -> None:
        """# FR-008 — 재료 추가 → 201."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.post(
            "/api/fridge", json={"raw_name": "두부", "quantity": "1모"}, headers=headers
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["raw_name"] == "두부"
        assert body["normalized_name"] == "두부"
        assert body["quantity"] == "1모"
        assert isinstance(body["id"], int)

    async def test_create_normalizes_synonym(self, async_client, test_jwt_token) -> None:
        """# SDD §3.2 — "쪽파" 입력 → "대파" 정규화 저장."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.post(
            "/api/fridge", json={"raw_name": "쪽파"}, headers=headers
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["raw_name"] == "쪽파", "원본 raw_name 보존"
        assert body["normalized_name"] == "대파", "SYNONYM_MAP 정규화 적용"

    async def test_create_normalizes_chili_synonym(
        self, async_client, test_jwt_token
    ) -> None:
        """# SDD §3.2 — "청양고추" → "고추" 정규화."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.post(
            "/api/fridge", json={"raw_name": "청양고추"}, headers=headers
        )
        assert resp.status_code == 201
        assert resp.json()["normalized_name"] == "고추"

    async def test_list_ingredients_returns_user_scoped(
        self, async_client, test_jwt_token, test_fridge
    ) -> None:
        """# FR-009 — 사용자별 재료 목록 조회."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.get("/api/fridge", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == len(test_fridge)
        names = {item["normalized_name"] for item in body["items"]}
        assert names == {"두부", "간장", "마늘", "밥", "계란"}

    async def test_delete_ingredient_returns_204(
        self, async_client, test_jwt_token, test_fridge
    ) -> None:
        """# FR-010 — 본인 재료 삭제 → 204."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        target_id = test_fridge[0]
        resp = await async_client.delete(f"/api/fridge/{target_id}", headers=headers)
        assert resp.status_code == 204

        # 재조회: 1개 감소
        resp = await async_client.get("/api/fridge", headers=headers)
        assert resp.json()["total"] == len(test_fridge) - 1

    async def test_delete_nonexistent_ingredient_returns_404(
        self, async_client, test_jwt_token
    ) -> None:
        """# FR-010 — 존재하지 않는 ID → 404."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.delete("/api/fridge/999999", headers=headers)
        assert resp.status_code == 404

    async def test_other_users_cannot_delete_my_ingredient(
        self, async_client, db_session, test_jwt_token, test_fridge
    ) -> None:
        """# FR-010·NFR-SEC-002 — 타 사용자가 본인 재료 삭제 시도 → 404 (혹은 403).

        구현은 사용자 격리를 위해 user_id 일치 조건으로 row 미선택 → 404 반환.
        """
        from sqlalchemy import update

        from app.models.orm import User

        # 다른 사용자 회원가입 + 이메일 인증 + 로그인
        await async_client.post(
            "/api/auth/signup",
            json={
                "email": "attacker@fridgechef.io",
                "password": "Attacker1!",
                "nickname": "공격자",
            },
        )
        await db_session.execute(
            update(User).where(User.email == "attacker@fridgechef.io").values(is_email_verified=True)
        )
        await db_session.commit()
        login = await async_client.post(
            "/api/auth/login",
            json={"email": "attacker@fridgechef.io", "password": "Attacker1!"},
        )
        attacker_token = login.json()["access_token"]
        target_id = test_fridge[0]
        resp = await async_client.delete(
            f"/api/fridge/{target_id}",
            headers={"Authorization": f"Bearer {attacker_token}"},
        )
        assert resp.status_code in (403, 404), "타 사용자 자원 접근 차단"

        # 원 소유자는 여전히 보유
        owner_headers = {"Authorization": test_jwt_token["Authorization"]}
        list_resp = await async_client.get("/api/fridge", headers=owner_headers)
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert target_id in ids, "공격 시도가 실패해도 원 소유자 데이터는 보존되어야 함"

    async def test_create_empty_raw_name_returns_422(
        self, async_client, test_jwt_token
    ) -> None:
        """# FR-008 — 빈 raw_name → 422 (Pydantic min_length=1)."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.post(
            "/api/fridge", json={"raw_name": ""}, headers=headers
        )
        assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────
class TestFridgeReturnPaths:
    """list·create·delete 반환 구조 검증 (AC-005~007)."""

    async def test_ac005_list_after_create_returns_item_fields(
        self, async_client, test_jwt_token
    ) -> None:
        """AC-005: 재료 1개 등록 후 목록 조회 → 200, items[0]에 id·raw_name 존재, total==1."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        await async_client.post("/api/fridge", json={"raw_name": "양파"}, headers=headers)
        resp = await async_client.get("/api/fridge", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert "id" in item
        assert item["raw_name"] == "양파"

    async def test_ac006_create_returns_id_and_raw_name(
        self, async_client, test_jwt_token
    ) -> None:
        """AC-006: POST /api/fridge {"raw_name": "양파"} → 201, 응답에 id·raw_name 포함."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.post(
            "/api/fridge", json={"raw_name": "양파"}, headers=headers
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body and isinstance(body["id"], int)
        assert body["raw_name"] == "양파"

    async def test_ac007_delete_nonexistent_ingredient_returns_404(
        self, async_client, test_jwt_token
    ) -> None:
        """AC-007: 존재하지 않는 ingredient_id 삭제 시도 → 404."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.delete("/api/fridge/99999", headers=headers)
        assert resp.status_code == 404


class TestFridgeEdgeCases:
    """엣지 케이스 — 중복·용량 제한."""

    @pytest.mark.xfail(
        reason="중복 재료 처리 정책(409 또는 idempotent merge)이 fridge_service에 미구현",
        strict=False,
    )
    async def test_create_duplicate_ingredient_handled(
        self, async_client, test_jwt_token
    ) -> None:
        """# FR-008 — 중복 재료 입력 → 409 또는 idempotent 응답."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        first = await async_client.post(
            "/api/fridge", json={"raw_name": "두부"}, headers=headers
        )
        assert first.status_code == 201
        dup = await async_client.post(
            "/api/fridge", json={"raw_name": "두부"}, headers=headers
        )
        # 정책: 409 또는 기존 row id 반환 (idempotent)
        assert dup.status_code in (409, 200, 201)
        if dup.status_code == 201:
            # idempotent: 동일 id
            assert dup.json()["id"] == first.json()["id"]

    @pytest.mark.xfail(
        reason="50개 초과 경고는 fridge_service 정책 추가 후 활성화 (현 라우터는 무제한 허용)",
        strict=False,
    )
    async def test_create_over_50_items_returns_warning(
        self, async_client, test_jwt_token
    ) -> None:
        """# FR-008 — 50개 초과 시 경고 헤더/필드 응답."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        for i in range(51):
            resp = await async_client.post(
                "/api/fridge", json={"raw_name": f"재료{i}"}, headers=headers
            )
            assert resp.status_code == 201
        list_resp = await async_client.get("/api/fridge", headers=headers)
        body = list_resp.json()
        assert body["total"] >= 51
        # 응답에 경고 플래그 (정책 정의 후 구현)
        assert body.get("warning") == "OVER_50_ITEMS" or "warning" in list_resp.headers
