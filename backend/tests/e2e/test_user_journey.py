"""페르소나 시나리오 E2E — SRS 부록 페르소나, SDD §3 UC-01~04.

- P1 김민준: 자취 1인 가구, 빠른 한끼 → 모델 A 결과 확인
- P2 이수진: 알레르기 영구 저장 (조개·땅콩) → 알레르기 위반 0건
- P3 박정희: 가족 4인분, 메인요리 선호
"""

from __future__ import annotations


class TestPersonaP1_Kim:
    """P1 김민준 — 자취·빠른 한끼·초보."""

    async def test_p1_signup_to_recommend_flow(
        self, async_client, mock_gemini_success
    ) -> None:
        """# UC-01·02·03 — 회원가입 → 냉장고 등록 → 추천."""
        # 1) 회원가입
        signup = await async_client.post(
            "/api/auth/signup",
            json={
                "email": "minjun@fridgechef.io",
                "password": "Minjun123!",
                "nickname": "김민준",
                "allergies": [],
            },
        )
        assert signup.status_code == 201

        # 2) 로그인
        login = await async_client.post(
            "/api/auth/login",
            json={"email": "minjun@fridgechef.io", "password": "Minjun123!"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3) 냉장고 등록 (자취생 보유 재료)
        for ing in ["두부", "간장", "마늘", "밥", "계란"]:
            r = await async_client.post(
                "/api/fridge", json={"raw_name": ing}, headers=headers
            )
            assert r.status_code == 201

        # 4) 추천 요청 (모델 A 결과 확보)
        rec = await async_client.post(
            "/api/recommend",
            json={
                "fridge_ingredients": ["두부", "간장", "마늘", "밥", "계란"],
                "preferences": {
                    "spicy": 2,
                    "difficulty": "초보",
                    "diet": False,
                    "use_saved_allergies": True,
                    "food_type": "메인요리",
                    "country": "한식",
                    "max_cook_min": 30,
                },
            },
        )
        assert rec.status_code == 200
        body = rec.json()
        assert len(body["model_a"]) >= 1, "P1: 모델 A 빠른 한끼 추천 결과 존재"
        # 빠른 한끼 — cook_min ≤ 30 보장
        for item in body["model_a"]:
            assert item["cook_min"] <= 30


class TestPersonaP2_Lee:
    """P2 이수진 — 알레르기 영구 저장 (조개·땅콩)."""

    async def test_p2_allergies_zero_exposure(
        self, async_client, mock_gemini_success
    ) -> None:
        """# NFR-EVAL-001·FR-007 — 저장 알레르기 자동 적용 → 위반 0건."""
        # 1) 알레르기 포함 회원가입
        signup = await async_client.post(
            "/api/auth/signup",
            json={
                "email": "sujin@fridgechef.io",
                "password": "Sujin1234!",
                "nickname": "이수진",
                "allergies": ["조개", "땅콩"],
            },
        )
        assert signup.status_code == 201

        # 2) 로그인
        login = await async_client.post(
            "/api/auth/login",
            json={"email": "sujin@fridgechef.io", "password": "Sujin1234!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3) 냉장고 등록
        for ing in ["두부", "간장", "마늘", "조개", "땅콩", "빵"]:
            await async_client.post(
                "/api/fridge", json={"raw_name": ing}, headers=headers
            )

        # 4) 추천 (use_saved_allergies=True + 헤더 알레르기)
        rec = await async_client.post(
            "/api/recommend",
            json={
                "fridge_ingredients": ["두부", "간장", "마늘", "조개", "땅콩", "빵"],
                "preferences": {
                    "use_saved_allergies": True,
                    "max_cook_min": 60,
                    "country": "한식",
                    "food_type": "메인요리",
                },
            },
            headers={"X-User-Allergies": "조개,땅콩"},
        )
        assert rec.status_code == 200
        body = rec.json()

        # 5) 알레르기 위반 0건 검증
        from app.models.recipe_repository import get_repository

        repo = get_repository()
        forbidden = {"조개", "땅콩"}
        for item in body["model_a"] + body["model_b"]:
            recipe = repo.get(item["recipe_id"])
            if recipe is None:
                continue
            assert not (set(recipe.allergens) & forbidden), (
                f"P2 알레르기 노출: {item['recipe_id']} allergens={recipe.allergens}"
            )


class TestPersonaP3_Park:
    """P3 박정희 — 가족 4인분, 메인요리·중급 난이도."""

    async def test_p3_family_main_dish_preference(
        self, async_client, mock_gemini_success
    ) -> None:
        """# FR-011 — 가족 4인분 → 메인요리·중급 난이도 추천."""
        # 1) 회원가입 + 로그인
        await async_client.post(
            "/api/auth/signup",
            json={
                "email": "junghee@fridgechef.io",
                "password": "Junghee123!",
                "nickname": "박정희",
                "allergies": [],
            },
        )
        login = await async_client.post(
            "/api/auth/login",
            json={"email": "junghee@fridgechef.io", "password": "Junghee123!"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2) 가족용 풍부한 냉장고
        family_fridge = ["두부", "간장", "마늘", "밥", "계란", "양파", "대파", "고추"]
        for ing in family_fridge:
            await async_client.post(
                "/api/fridge", json={"raw_name": ing}, headers=headers
            )

        # 3) 가족 4인분 추천
        rec = await async_client.post(
            "/api/recommend",
            json={
                "fridge_ingredients": family_fridge,
                "preferences": {
                    "spicy": 2,
                    "difficulty": "중급",
                    "food_type": "메인요리",
                    "country": "한식",
                    "max_cook_min": 60,
                    "use_saved_allergies": False,
                    "user_context": "가족 4인분 저녁식사",
                },
            },
        )
        assert rec.status_code == 200
        body = rec.json()
        assert len(body["model_a"]) >= 1, "P3: 모델 A 가족식 결과 존재"
        # 모델 A 메인 우선 — main 테마 비율이 0이면 안 됨 (한식 메인 카탈로그 가정)
        main_count = sum(1 for r in body["model_a"] if r["theme"] == "main")
        assert main_count >= 1, "P3: 메인요리가 모델 A 에 최소 1건 포함"
