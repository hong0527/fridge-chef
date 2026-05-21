"""통합 테스트 — /api/auth/me 엔드포인트 (AI 생성)"""
import pytest
from httpx import AsyncClient

from app.core.rate_limit import _attempts


@pytest.fixture(autouse=True)
def clear_rate_limit():
    """테스트 간 rate_limit 상태 초기화."""
    _attempts.clear()
    yield
    _attempts.clear()


@pytest.mark.asyncio
class TestGetMe:
    async def test_get_me_success(self, auth_client: AsyncClient):
        resp = await auth_client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data
        assert "nickname" in data
        assert "allergies" in data

    async def test_get_me_no_token(self, async_client: AsyncClient):
        resp = await async_client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_get_me_invalid_token(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalidtoken"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestPatchMe:
    async def test_patch_nickname(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/auth/me", json={"nickname": "새닉네임"}
        )
        assert resp.status_code == 200
        assert resp.json()["nickname"] == "새닉네임"

    async def test_patch_empty_body_422(self, auth_client: AsyncClient):
        resp = await auth_client.patch("/api/auth/me", json={})
        assert resp.status_code == 422

    async def test_patch_wrong_current_password(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/auth/me",
            json={"current_password": "wrongpw", "new_password": "newpass123"},
        )
        assert resp.status_code == 400

    async def test_patch_password_success(
        self, auth_client: AsyncClient, test_user_password: str
    ):
        resp = await auth_client.patch(
            "/api/auth/me",
            json={
                "current_password": test_user_password,
                "new_password": "newvalidpass",
            },
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestPatchMeAllergies:
    async def test_update_allergies(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/auth/me/allergies",
            json={"allergies": ["땅콩", "새우"]},
        )
        assert resp.status_code == 200
        assert "땅콩" in resp.json()["allergies"]

    async def test_clear_allergies(self, auth_client: AsyncClient):
        resp = await auth_client.patch(
            "/api/auth/me/allergies", json={"allergies": []}
        )
        assert resp.status_code == 200
        assert resp.json()["allergies"] == []


@pytest.mark.asyncio
class TestLoginRateLimit:
    async def test_sixth_attempt_returns_423(self, async_client: AsyncClient, test_user_email: str):
        for _ in range(5):
            await async_client.post(
                "/api/auth/login",
                json={"email": test_user_email, "password": "wrongpw"},
            )
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": test_user_email, "password": "wrongpw"},
        )
        assert resp.status_code == 423

    async def test_success_clears_attempts(
        self, async_client: AsyncClient, test_user_email: str, test_user_password: str
    ):
        for _ in range(3):
            await async_client.post(
                "/api/auth/login",
                json={"email": test_user_email, "password": "wrongpw"},
            )
        await async_client.post(
            "/api/auth/login",
            json={"email": test_user_email, "password": test_user_password},
        )
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": test_user_email, "password": "wrongpw"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestExistingEndpointsRegression:
    async def test_signup_still_works(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/api/auth/signup",
            json={
                "email": "regression@test.com",
                "password": "testpass1",
                "nickname": "회귀테스트",
                "allergies": [],
            },
        )
        assert resp.status_code == 201

    async def test_login_still_works(
        self, async_client: AsyncClient, test_user_email: str, test_user_password: str
    ):
        await async_client.post("/api/auth/signup", json={
            "email": test_user_email,
            "password": test_user_password,
            "nickname": "테스터",
            "allergies": [],
        })
        resp = await async_client.post(
            "/api/auth/login",
            json={"email": test_user_email, "password": test_user_password},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
