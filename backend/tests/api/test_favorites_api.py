"""즐겨찾기 API 통합 테스트 — 이슈 #49.

- POST   /api/favorites/{recipe_id}  즐겨찾기 추가
- DELETE /api/favorites/{recipe_id}  즐겨찾기 삭제
- GET    /api/favorites/{recipe_id}  즐겨찾기 여부 확인
- GET    /api/favorites              즐겨찾기 목록 조회
- NFR-SEC-002: 모든 엔드포인트 JWT 필수
"""

from __future__ import annotations

from app.models.orm import RecipeRow

_RECIPE_ID = "test-recipe-001"


async def _seed_recipe(db_session, recipe_id: str = _RECIPE_ID) -> RecipeRow:
    row = RecipeRow(
        recipe_id=recipe_id,
        name="테스트라면",
        whole_ingredients=["면", "계란"],
        steps=[],
        cook_min=10,
        spicy=3,
        difficulty_level=1,
        is_low_calorie=False,
        country="kr",
        theme="main",
        allergens=["밀", "계란"],
    )
    db_session.add(row)
    await db_session.commit()
    return row


# ─────────────────────────────────────────────────────────────
class TestFavoritesAuth:
    """JWT 가드 — NFR-SEC-002."""

    async def test_list_without_token_returns_401(self, async_client) -> None:
        resp = await async_client.get("/api/favorites")
        assert resp.status_code == 401

    async def test_check_without_token_returns_401(self, async_client) -> None:
        resp = await async_client.get(f"/api/favorites/{_RECIPE_ID}")
        assert resp.status_code == 401

    async def test_add_without_token_returns_401(self, async_client) -> None:
        resp = await async_client.post(f"/api/favorites/{_RECIPE_ID}")
        assert resp.status_code == 401

    async def test_delete_without_token_returns_401(self, async_client) -> None:
        resp = await async_client.delete(f"/api/favorites/{_RECIPE_ID}")
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────
class TestFavoritesCRUD:
    """POST/DELETE/GET /api/favorites — 기본 동작."""

    async def test_add_favorite_returns_201(self, async_client, test_jwt_token) -> None:
        """즐겨찾기 추가 → 201."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        assert resp.status_code == 201

    async def test_check_favorite_true_after_add(self, async_client, test_jwt_token) -> None:
        """추가 후 조회 → is_favorite: true."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        resp = await async_client.get(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_favorite"] is True

    async def test_check_favorite_false_when_not_added(self, async_client, test_jwt_token) -> None:
        """추가 안 한 레시피 조회 → is_favorite: false."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.get("/api/favorites/nonexistent-recipe", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_favorite"] is False

    async def test_delete_favorite_returns_204(self, async_client, test_jwt_token) -> None:
        """추가 후 삭제 → 204."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        resp = await async_client.delete(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        assert resp.status_code == 204

    async def test_check_favorite_false_after_delete(self, async_client, test_jwt_token) -> None:
        """삭제 후 조회 → is_favorite: false."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        await async_client.delete(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        resp = await async_client.get(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        assert resp.json()["is_favorite"] is False

    async def test_delete_nonexistent_returns_404(self, async_client, test_jwt_token) -> None:
        """없는 즐겨찾기 삭제 → 404."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.delete("/api/favorites/nonexistent-recipe", headers=headers)
        assert resp.status_code == 404

    async def test_list_includes_added_recipe(
        self, async_client, test_jwt_token, db_session
    ) -> None:
        """추가한 레시피가 목록에 포함됨."""
        await _seed_recipe(db_session, _RECIPE_ID)
        headers = {"Authorization": test_jwt_token["Authorization"]}
        await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        resp = await async_client.get("/api/favorites", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["recipe_id"] == _RECIPE_ID
        assert body["items"][0]["name"] == "테스트라면"

    async def test_list_empty_initially(self, async_client, test_jwt_token) -> None:
        """즐겨찾기 없을 때 빈 목록."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        resp = await async_client.get("/api/favorites", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    async def test_list_excludes_deleted_recipe(
        self, async_client, test_jwt_token, db_session
    ) -> None:
        """삭제한 레시피는 목록에서 제외됨."""
        await _seed_recipe(db_session, _RECIPE_ID)
        headers = {"Authorization": test_jwt_token["Authorization"]}
        await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        await async_client.delete(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        resp = await async_client.get("/api/favorites", headers=headers)
        assert resp.json()["total"] == 0


# ─────────────────────────────────────────────────────────────
class TestFavoritesEdgeCases:
    """엣지 케이스 — 중복·사용자 격리."""

    async def test_add_duplicate_is_idempotent(self, async_client, test_jwt_token) -> None:
        """중복 추가 → 201 (idempotent, 오류 없음)."""
        headers = {"Authorization": test_jwt_token["Authorization"]}
        first = await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        second = await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        assert first.status_code == 201
        assert second.status_code == 201

    async def test_duplicate_does_not_create_two_rows(
        self, async_client, test_jwt_token, db_session
    ) -> None:
        """중복 추가해도 목록에 1개만."""
        await _seed_recipe(db_session, _RECIPE_ID)
        headers = {"Authorization": test_jwt_token["Authorization"]}
        await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        resp = await async_client.get("/api/favorites", headers=headers)
        assert resp.json()["total"] == 1

    async def test_other_user_cannot_see_my_favorites(
        self, async_client, test_jwt_token, db_session
    ) -> None:
        """다른 사용자의 즐겨찾기는 보이지 않음 — 사용자 격리."""
        from sqlalchemy import update

        from app.models.orm import User

        headers = {"Authorization": test_jwt_token["Authorization"]}
        await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)

        # 다른 사용자 생성 + 인증
        await async_client.post("/api/auth/signup", json={
            "email": "other@fridgechef.io",
            "password": "Other1234!",
            "nickname": "다른유저",
        })
        await db_session.execute(
            update(User).where(User.email == "other@fridgechef.io").values(is_email_verified=True)
        )
        await db_session.commit()
        login = await async_client.post("/api/auth/login", json={
            "email": "other@fridgechef.io",
            "password": "Other1234!",
        })
        other_token = login.json()["access_token"]

        resp = await async_client.get(
            "/api/favorites", headers={"Authorization": f"Bearer {other_token}"}
        )
        assert resp.json()["total"] == 0

    async def test_other_user_cannot_delete_my_favorite(
        self, async_client, test_jwt_token, db_session
    ) -> None:
        """다른 사용자가 내 즐겨찾기 삭제 시도 → 404."""
        from sqlalchemy import update

        from app.models.orm import User

        headers = {"Authorization": test_jwt_token["Authorization"]}
        await async_client.post(f"/api/favorites/{_RECIPE_ID}", headers=headers)

        await async_client.post("/api/auth/signup", json={
            "email": "attacker@fridgechef.io",
            "password": "Attacker1!",
            "nickname": "공격자",
        })
        await db_session.execute(
            update(User).where(User.email == "attacker@fridgechef.io").values(is_email_verified=True)
        )
        await db_session.commit()
        login = await async_client.post("/api/auth/login", json={
            "email": "attacker@fridgechef.io",
            "password": "Attacker1!",
        })
        attacker_token = login.json()["access_token"]

        resp = await async_client.delete(
            f"/api/favorites/{_RECIPE_ID}",
            headers={"Authorization": f"Bearer {attacker_token}"},
        )
        assert resp.status_code == 404

        # 원 소유자 즐겨찾기는 유지됨
        check = await async_client.get(f"/api/favorites/{_RECIPE_ID}", headers=headers)
        assert check.json()["is_favorite"] is True
