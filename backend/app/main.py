"""FastAPI 엔트리포인트 (SDD §1.3 Presentation Layer).

- NFR-PERF-001: 추천 응답 ≤ 10초 (recommend 라우터에서 타임아웃 가드)
- NFR-SEC-001: CORS·환경변수 격리
- NFR-OPS-001: /health 헬스체크
- startup lifespan: 인메모리 SEED_RECIPES 를 DB `recipes` 테이블에 idempotent 적재.
  이로써 /api/recommend (인메모리) 와 /api/recipes/{id} (DB) 출처가 일치한다.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app import __version__
from app.api import auth, fridge, recipes, recommend
from app.core.db import AsyncSessionLocal
from app.models.orm import RecipeRow
from app.models.recipe_repository import SEED_RECIPES

_logger = logging.getLogger("app.main")

_ENV = os.getenv("ENV", "dev")
_DOCS_ENABLED = _ENV != "production"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """SEED_RECIPES → DB idempotent 적재. 추천(인메모리)·상세(DB) 일관성 보장.

    Cross-dialect idempotent 패턴: 기존 recipe_id 사전 조회 → 누락분만 INSERT.
    단일 워커 가정. 다중 워커 운영 시 advisory lock 또는 postgres ON CONFLICT 권장.
    """
    try:
        async with AsyncSessionLocal() as db:
            existing_ids = set(
                (await db.scalars(select(RecipeRow.recipe_id))).all()
            )
            new_rows = [
                RecipeRow(
                    recipe_id=r.recipe_id,
                    name=r.name,
                    whole_ingredients=r.whole_ingredients,
                    steps=[],
                    cook_min=r.cook_min,
                    spicy=r.spicy,
                    difficulty_level=r.difficulty_level,
                    is_low_calorie=r.is_low_calorie,
                    country=r.country,
                    theme=r.theme,
                    allergens=r.allergens,
                )
                for r in SEED_RECIPES
                if r.recipe_id not in existing_ids
            ]
            if new_rows:
                db.add_all(new_rows)
                await db.commit()
                _logger.info("startup seed: %d/%d new recipes inserted", len(new_rows), len(SEED_RECIPES))
            else:
                _logger.info("startup seed: all %d recipes already present", len(SEED_RECIPES))
    except Exception as exc:  # noqa: BLE001 — startup 실패 시 부팅은 진행
        _logger.warning("startup seed failed (skipping): %s", exc)
    yield


app = FastAPI(
    title="FridgeChef API",
    version=__version__,
    description="냉장고 재료 기반 AI 레시피 추천 (Model A 냉털 / Model B 부족재료 / Gemini 자연어)",
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    lifespan=lifespan,
)

# NFR-SEC-001 — CORS: 명시 화이트리스트만 허용 (와일드카드 + credentials 조합 금지)
_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    # Bearer 토큰만 사용 (쿠키 인증 X) → credentials 불필요. 향후 쿠키 도입 시 True.
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    max_age=600,
)

# 라우터 등록 (SDD §1.3 API 레이어)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(fridge.router, prefix="/api/fridge", tags=["fridge"])
app.include_router(recommend.router, prefix="/api/recommend", tags=["recommend"])
app.include_router(recipes.router, prefix="/api/recipes", tags=["recipes"])


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """NFR-OPS-001 — 헬스체크 (CI·로드밸런서용)."""
    return {"status": "ok", "version": __version__}


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"service": "fridge-chef", "docs": "/docs"}
