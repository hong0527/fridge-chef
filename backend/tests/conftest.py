"""Pytest fixtures — SQLite in-memory + JWT helpers + Gemini mock 표준화.

SRS/SDD 정합 — 다음 픽스처를 제공:
- `db_engine`           : aiosqlite 인메모리 엔진 (PostgreSQL ↔ SQLite 호환 회피 — JSON, datetime)
- `db_session`          : 트랜잭션 격리 세션 (각 테스트 후 rollback)
- `app`                 : 의존성 오버라이드된 FastAPI 인스턴스
- `async_client`        : httpx.AsyncClient (ASGI transport, 비동기 표준)
- `client`              : 기존 sync TestClient 호환 유지 (test_health 등)
- `test_user`           : 회원가입 + 응답 dict
- `test_jwt_token`      : 토큰 + 헤더 dict
- `test_fridge`         : 사전 등록된 냉장고 재료 ID 리스트
- `mock_gemini_success` : 성공 모킹 헬퍼
- `mock_gemini_fail`    : 실패 모킹 헬퍼
- `recipe_repo`         : 결정론적 미니 카탈로그

NOTE: 외부 의존성 (Postgres/Gemini) 차단 — 모든 테스트는 격리 보장.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

# ─── PYTHONPATH 보정 ─────────────────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ─── 테스트 전용 환경변수 (app 임포트 전에 설정) ───────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
# 32자 이상 시크릿 (security.py 부팅 가드 충족 — 테스트 전용, 운영 사용 금지)
os.environ.setdefault(
    "JWT_SECRET",
    "test-secret-do-not-use-in-prod-padding-1234567890abcdef",
)
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_EXPIRE_MIN", "60")
os.environ.setdefault("GEMINI_API_KEY", "")  # 빈 키 → 폴백 강제
os.environ.setdefault("RECOMMEND_TIMEOUT_S", "10.0")


# ─── pytest-asyncio 모드 (pyproject 에서 auto 지정) ────────────


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """세션 스코프 이벤트 루프 — async_client/db_engine 공유."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── DB 픽스처 ────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="function")
async def db_engine():  # type: ignore[no-untyped-def]
    """함수 스코프 SQLite-인메모리 엔진 + 테이블 생성/해제."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core.db import Base
    from app.models import orm as _orm  # noqa: F401 — 모델 import 유도

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):  # type: ignore[no-untyped-def]
    """단일 트랜잭션 세션 — 함수 종료 후 rollback (격리)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    SessionLocal = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session


# ─── FastAPI app + dependency override ────────────────────────


@pytest_asyncio.fixture
async def app(db_engine):  # type: ignore[no-untyped-def]
    """의존성을 SQLite 엔진으로 오버라이드한 FastAPI 인스턴스."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.db import get_db
    from app.main import app as fastapi_app

    SessionLocal = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def _override_get_db():
        async with SessionLocal() as s:
            yield s

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(app):  # type: ignore[no-untyped-def]
    """httpx.AsyncClient — FastAPI 비동기 테스트 표준 (ASGI transport)."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session")
def client():  # type: ignore[no-untyped-def]
    """레거시 sync TestClient — test_health 호환."""
    from fastapi.testclient import TestClient

    from app.main import app as fastapi_app

    return TestClient(fastapi_app)


# ─── 인증 픽스처 ──────────────────────────────────────────────


@pytest_asyncio.fixture
async def test_user(async_client, db_session) -> dict[str, Any]:
    """기본 회원가입 사용자. password 평문 포함 (재로그인용)."""
    from sqlalchemy import update

    from app.models.orm import User

    payload = {
        "email": "tester@fridgechef.io",
        "password": "Test1234!",
        "nickname": "테스터",
        "allergies": [],
    }
    resp = await async_client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 201, f"signup 실패: {resp.text}"

    # 테스트 환경에서는 이메일 인증 없이 바로 활성화
    await db_session.execute(
        update(User).where(User.email == payload["email"]).values(is_email_verified=True)
    )
    await db_session.commit()

    data = resp.json()
    data["password"] = payload["password"]
    return data


@pytest_asyncio.fixture
async def test_jwt_token(async_client, test_user) -> dict[str, str]:
    """로그인 후 Bearer 헤더 dict 반환."""
    resp = await async_client.post(
        "/api/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    assert resp.status_code == 200, f"login 실패: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "_token": token}


@pytest_asyncio.fixture
async def test_fridge(async_client, test_jwt_token) -> list[int]:
    """사전 등록 냉장고: 두부·간장·마늘·밥·계란 → ID 리스트."""
    headers = {"Authorization": test_jwt_token["Authorization"]}
    ingredients = ["두부", "간장", "마늘", "밥", "계란"]
    ids: list[int] = []
    for ing in ingredients:
        resp = await async_client.post(
            "/api/fridge", json={"raw_name": ing}, headers=headers
        )
        assert resp.status_code == 201, f"fridge 등록 실패: {resp.text}"
        ids.append(resp.json()["id"])
    return ids


# ─── Gemini 모킹 헬퍼 ─────────────────────────────────────────


@pytest.fixture
def mock_gemini_success(monkeypatch):  # type: ignore[no-untyped-def]
    """Gemini 가 항상 상위 3개를 그대로 반환하도록 모킹."""
    from app.services import model_b as mb_mod

    async def _mock(candidates: list[dict], user_context: str) -> dict[str, Any]:
        ids = [c["recipe_id"] for c in candidates[:3]]
        return {
            "selected": ids,
            "reasons": [f"{rid} Gemini 추천 이유" for rid in ids],
            "citation_ids": ids,
        }

    monkeypatch.setattr(mb_mod, "gemini_select_top3", _mock)
    return _mock


@pytest.fixture
def mock_gemini_fail(monkeypatch):  # type: ignore[no-untyped-def]
    """Gemini 가 항상 None 반환 (타임아웃·오류 시나리오)."""
    from app.services import model_b as mb_mod

    async def _mock(candidates: list[dict], user_context: str) -> None:
        return None

    monkeypatch.setattr(mb_mod, "gemini_select_top3", _mock)
    return _mock


# ─── 결정론적 레시피 카탈로그 ─────────────────────────────────


@pytest.fixture
def recipe_repo():  # type: ignore[no-untyped-def]
    """결정론적 미니 카탈로그 — 모델 A/B 알고리즘 단위 테스트용."""
    from app.core.synonym_map import normalize_list
    from app.models.recipe import Recipe
    from app.models.recipe_repository import RecipeRepository

    recipes = [
        Recipe(
            "t001",
            "간장계란밥",
            normalize_list(["밥", "계란", "간장"]),
            cook_min=10,
            spicy=1,
            difficulty_level=1,
            country="kr",
            theme="main",
            allergens=normalize_list(["계란"]),
        ),
        Recipe(
            "t002",
            "두부조림",
            normalize_list(["두부", "간장", "마늘"]),
            cook_min=20,
            spicy=2,
            difficulty_level=1,
            country="kr",
            theme="main",
            allergens=normalize_list(["대두"]),
        ),
        Recipe(
            "t003",
            "닭가슴살구이",
            normalize_list(["닭가슴살", "올리브유"]),
            cook_min=15,
            spicy=1,
            difficulty_level=1,
            is_low_calorie=True,
            country="west",
            theme="main",
            allergens=normalize_list(["닭고기"]),
        ),
        Recipe(
            "t004",
            "파스타",
            normalize_list(["면", "치즈", "마늘"]),
            cook_min=25,
            spicy=1,
            difficulty_level=2,
            country="west",
            theme="main",
            allergens=normalize_list(["밀", "우유"]),
        ),
        Recipe(
            "t005",
            "야채볶음",
            normalize_list(["양파", "버섯", "당근"]),
            cook_min=15,
            spicy=1,
            difficulty_level=1,
            is_low_calorie=True,
            theme="side",
        ),
        Recipe(
            "t006",
            "조개탕",
            normalize_list(["조개", "마늘", "대파"]),
            cook_min=20,
            spicy=1,
            difficulty_level=2,
            theme="soup",
            allergens=normalize_list(["조개"]),
        ),
        Recipe(
            "t007",
            "땅콩버터샌드",
            normalize_list(["빵", "땅콩"]),
            cook_min=5,
            spicy=1,
            difficulty_level=1,
            country="west",
            theme="main",
            allergens=normalize_list(["땅콩", "밀"]),
        ),
    ]
    return RecipeRepository(recipes)


# ─── auth_client fixture (test_auth_me_api 전용) ──────────────

_TEST_EMAIL = "testme@test.com"
_TEST_PASSWORD = "testpass1"


@pytest.fixture
def test_user_email() -> str:
    return _TEST_EMAIL


@pytest.fixture
def test_user_password() -> str:
    return _TEST_PASSWORD


@pytest_asyncio.fixture
async def auth_client(async_client, db_session):
    """로그인된 상태의 AsyncClient — /api/auth/me 테스트 전용."""
    from sqlalchemy import update

    from app.models.orm import User

    await async_client.post("/api/auth/signup", json={
        "email": _TEST_EMAIL,
        "password": _TEST_PASSWORD,
        "nickname": "테스터",
        "allergies": [],
    })

    # 테스트 환경에서는 이메일 인증 없이 바로 활성화
    await db_session.execute(
        update(User).where(User.email == _TEST_EMAIL).values(is_email_verified=True)
    )
    await db_session.commit()

    resp = await async_client.post("/api/auth/login", json={
        "email": _TEST_EMAIL,
        "password": _TEST_PASSWORD,
    })
    token = resp.json()["access_token"]
    async_client.headers["Authorization"] = f"Bearer {token}"
    return async_client
