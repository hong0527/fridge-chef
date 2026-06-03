"""Supabase 적재 — 로컬 postgres 1667 레시피 + 이미지 1667장을 Supabase로 옮김.

흐름:
1. 환경변수 검증 (SUPABASE_DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET)
2. Supabase DB에 ORM 테이블 생성 (Base.metadata.create_all)
3. 로컬 postgres에서 1667 레시피 SELECT
4. Storage `recipe-images` 버킷에 이미지 1667장 upsert (이미 있으면 skip)
5. Supabase recipes 테이블에 INSERT (image_url = Storage 공개 URL)
6. 검증 (count, 샘플 URL fetch)

실행: cd backend && python scripts/upload_to_supabase.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import ssl
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("supabase-upload")

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))

# .env 로드 (호스트 실행 시)
_DOTENV = _BACKEND_DIR.parent / ".env"
if _DOTENV.is_file():
    for line in _DOTENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

# ─── 검증 ────────────────────────────────────────────
REQUIRED = [
    "SUPABASE_DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_BUCKET",
    "DATABASE_URL",  # 로컬 source
]
missing = [k for k in REQUIRED if not os.getenv(k)]
if missing:
    log.error("환경변수 누락: %s", missing)
    sys.exit(1)

SUPA_DB_URL = os.environ["SUPABASE_DATABASE_URL"]
SUPA_URL = os.environ["SUPABASE_URL"]
SUPA_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SUPA_BUCKET = os.environ["SUPABASE_BUCKET"]
LOCAL_DB_URL = os.environ["DATABASE_URL"]
IMG_DIR = _BACKEND_DIR / "data" / "recipes_images"

# JWT_SECRET 미설정 시 ORM import 실패 방지 (스크립트 전용 더미)
os.environ.setdefault(
    "JWT_SECRET",
    "supabase-upload-script-dummy-secret-padding-1234567890abcdef",
)

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from supabase import create_client  # noqa: E402

from app.core.db import Base  # noqa: E402
from app.models.orm import RecipeRow  # noqa: E402


def storage_public_url(recipe_id: str) -> str:
    """Supabase Storage 공개 URL 형식 (Public bucket 전제)."""
    return f"{SUPA_URL}/storage/v1/object/public/{SUPA_BUCKET}/{recipe_id}.jpg"


async def ensure_tables(engine) -> None:
    """ORM 테이블 자동 생성 (Alembic 없이도 적재 가능하게)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Supabase: 테이블 생성/검증 완료")


def upload_images(supa) -> tuple[int, int]:
    """이미지 1667장을 Storage에 upsert. 반환: (성공, 실패)."""
    if not IMG_DIR.is_dir():
        log.error("이미지 디렉터리 없음: %s", IMG_DIR)
        return 0, 0
    files = sorted(IMG_DIR.glob("*.jpg"))
    total = len(files)
    log.info("이미지 업로드 시작 — %d장", total)
    ok, ng = 0, 0
    for i, fp in enumerate(files, 1):
        try:
            with fp.open("rb") as f:
                supa.storage.from_(SUPA_BUCKET).upload(
                    path=fp.name,
                    file=f.read(),
                    file_options={
                        "content-type": "image/jpeg",
                        "upsert": "true",
                    },
                )
            ok += 1
        except Exception as exc:
            msg = str(exc)
            # 이미 존재하면 OK 처리 (upsert가 무력화돼도)
            if "Duplicate" in msg or "already exists" in msg or "409" in msg:
                ok += 1
            else:
                ng += 1
                if ng <= 5:
                    log.warning("업로드 실패 %s: %s", fp.name, msg[:120])
        if i % 100 == 0:
            log.info("  진행: %d/%d (ok=%d ng=%d)", i, total, ok, ng)
    log.info("이미지 업로드 완료 — ok=%d, ng=%d", ok, ng)
    return ok, ng


async def copy_recipes(local_engine, supa_engine) -> int:
    """로컬 recipes 전체를 Supabase recipes로 upsert (image_url 갱신)."""
    LocalSession = async_sessionmaker(local_engine, expire_on_commit=False)
    SupaSession = async_sessionmaker(supa_engine, expire_on_commit=False)
    async with LocalSession() as ls, SupaSession() as ss:
        rows = (await ls.scalars(select(RecipeRow))).all()
        log.info("로컬에서 %d 레시피 읽음", len(rows))
        # 배치 INSERT ... ON CONFLICT DO UPDATE
        batch = []
        for r in rows:
            batch.append({
                "recipe_id": r.recipe_id,
                "name": r.name,
                "whole_ingredients": list(r.whole_ingredients or []),
                "steps": list(r.steps or []),
                "cook_min": r.cook_min,
                "spicy": r.spicy,
                "difficulty_level": r.difficulty_level,
                "is_low_calorie": r.is_low_calorie,
                "country": r.country,
                "theme": r.theme,
                "allergens": list(r.allergens or []),
                "image_url": storage_public_url(r.recipe_id),
            })
        # 100개씩 끊어 INSERT (pooler 안정)
        CHUNK = 100
        inserted = 0
        for i in range(0, len(batch), CHUNK):
            sub = batch[i : i + CHUNK]
            stmt = pg_insert(RecipeRow).values(sub)
            stmt = stmt.on_conflict_do_update(
                index_elements=["recipe_id"],
                set_={
                    c.name: stmt.excluded[c.name]
                    for c in RecipeRow.__table__.columns
                    if c.name not in ("id", "created_at")
                },
            )
            await ss.execute(stmt)
            await ss.commit()
            inserted += len(sub)
            log.info("  recipes upsert: %d/%d", inserted, len(batch))
        return inserted


async def verify(supa_engine) -> dict:
    """Supabase recipes 카운트 + 샘플 1건."""
    SupaSession = async_sessionmaker(supa_engine, expire_on_commit=False)
    async with SupaSession() as s:
        n = (await s.scalars(select(RecipeRow))).all()
        if not n:
            return {"count": 0}
        sample = n[0]
        return {
            "count": len(n),
            "sample_id": sample.recipe_id,
            "sample_name": sample.name,
            "sample_image_url": sample.image_url,
        }


async def main() -> None:
    log.info("=== Supabase 적재 시작 ===")
    log.info("Supabase URL: %s", SUPA_URL)
    log.info("Bucket: %s", SUPA_BUCKET)

    # Engine: pooler 안정성 위해 statement_cache_size=0
    # SSL: macOS+anaconda 인증서 체인 문제 우회 — Supabase는 SSL 강제하지만 self-signed 검증은 skip.
    # 학부 일회성 적재용 (운영에선 certifi cafile 권장).
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    supa_engine = create_async_engine(
        SUPA_DB_URL,
        connect_args={"statement_cache_size": 0, "ssl": ssl_ctx},
        pool_pre_ping=True,
    )
    local_engine = create_async_engine(LOCAL_DB_URL, pool_pre_ping=True)

    # 1) 테이블 생성
    await ensure_tables(supa_engine)

    # 2) 이미지 업로드 (동기 supabase-py)
    supa = create_client(SUPA_URL, SUPA_KEY)
    ok, ng = upload_images(supa)
    if ok == 0 and ng > 0:
        log.error("이미지 업로드 모두 실패 — 중단")
        sys.exit(2)

    # 3) 레시피 텍스트 적재
    inserted = await copy_recipes(local_engine, supa_engine)
    log.info("recipes upsert 합계: %d", inserted)

    # 4) 검증
    v = await verify(supa_engine)
    log.info("=== 검증 결과 ===")
    log.info("Supabase recipes count: %s", v.get("count"))
    log.info("샘플 ID: %s | name: %s", v.get("sample_id"), v.get("sample_name"))
    log.info("샘플 image_url: %s", v.get("sample_image_url"))

    await supa_engine.dispose()
    await local_engine.dispose()
    log.info("=== 완료 ===")


if __name__ == "__main__":
    asyncio.run(main())
