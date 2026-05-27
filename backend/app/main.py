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
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app import __version__
from app.api import auth, fridge, recipes, recommend
from app.core.db import AsyncSessionLocal
from app.models.orm import RecipeRow
from app.models.recipe import Recipe
from app.models.recipe_repository import SEED_RECIPES, RecipeRepository, set_repository

_logger = logging.getLogger("app.main")

_ENV = os.getenv("ENV", "dev")
_DOCS_ENABLED = _ENV != "production"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """SEED → DB idempotent 적재 + **DB → 인메모리 repo 갱신**.

    추천 알고리즘(model_a/b)은 `get_repository()` 의 인메모리 RecipeRepository를 본다.
    DB에 대규모 레시피(1667+)가 적재된 경우 인메모리 repo도 같은 데이터로 갱신해야
    추천 결과가 DB와 일치한다.
    """
    try:
        async with AsyncSessionLocal() as db:
            existing_ids = set(
                (await db.scalars(select(RecipeRow.recipe_id))).all()
            )
            # SEED 적재는 DB가 비어있을 때만 (외부 ETL로 적재된 대규모 데이터셋 보존).
            if len(existing_ids) < len(SEED_RECIPES):
                new_rows = [
                    RecipeRow(
                        recipe_id=r.recipe_id, name=r.name,
                        whole_ingredients=r.whole_ingredients, steps=[],
                        cook_min=r.cook_min, spicy=r.spicy,
                        difficulty_level=r.difficulty_level,
                        is_low_calorie=r.is_low_calorie,
                        country=r.country, theme=r.theme, allergens=r.allergens,
                    )
                    for r in SEED_RECIPES
                    if r.recipe_id not in existing_ids
                ]
                if new_rows:
                    db.add_all(new_rows)
                    await db.commit()
                    _logger.info("startup seed: %d new recipes inserted", len(new_rows))
            else:
                _logger.info("startup seed skipped: DB has %d recipes (>= SEED %d)",
                             len(existing_ids), len(SEED_RECIPES))

            # DB → 인메모리 repo 갱신 — 추천 알고리즘이 DB 전체 카탈로그를 보도록.
            rows = (await db.scalars(select(RecipeRow))).all()
            domain_recipes = [
                Recipe(
                    recipe_id=row.recipe_id, name=row.name,
                    whole_ingredients=list(row.whole_ingredients or []),
                    cook_min=row.cook_min, spicy=row.spicy,
                    difficulty_level=row.difficulty_level,
                    is_low_calorie=row.is_low_calorie,
                    country=row.country, theme=row.theme,
                    allergens=list(row.allergens or []),
                )
                for row in rows
            ]
            set_repository(RecipeRepository(domain_recipes))
            _logger.info("startup repo loaded from DB: %d recipes (인메모리 갱신)", len(domain_recipes))
    except Exception:
        # 광역 예외이지만 traceback을 보존해 운영 사일런트 실패 방지 (code-reviewer HIGH 수정).
        # SEED 35건 fallback으로 부팅은 계속 진행.
        _logger.exception("startup seed/load failed — falling back to in-memory SEED")
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
from app.api import ingredients  # noqa: E402

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(fridge.router, prefix="/api/fridge", tags=["fridge"])
app.include_router(recommend.router, prefix="/api/recommend", tags=["recommend"])
app.include_router(recipes.router, prefix="/api/recipes", tags=["recipes"])
app.include_router(ingredients.router, prefix="/api/ingredients", tags=["ingredients"])

# 정적 이미지 서빙 — backend/data/recipes_images/{cookid}.jpg → /static/recipes/{cookid}.jpg
# code-reviewer HIGH 수정: Path.resolve()로 정규화 (CWD 의존 제거 + traversal 방어 보강)
_STATIC_RECIPES_DIR = (Path(__file__).resolve().parent.parent / "data" / "recipes_images").resolve()
if _STATIC_RECIPES_DIR.is_dir():
    app.mount(
        "/static/recipes",
        StaticFiles(directory=str(_STATIC_RECIPES_DIR)),
        name="recipes_images",
    )


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """NFR-OPS-001 — 헬스체크 (CI·로드밸런서용)."""
    return {"status": "ok", "version": __version__}


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"service": "fridge-chef", "docs": "/docs"}
