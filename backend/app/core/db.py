"""SQLAlchemy DB 세션 (SDD §1.3 Data Layer).

- 비동기 엔진: asyncpg 드라이버
- 의존성 주입: FastAPI Depends(get_db)
- NFR-PERF-002: 풀 사이즈 10, 오버플로우 20
"""

from __future__ import annotations

import os
import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# 환경변수에서 직접 로드 (config.py 의 dataclass Settings 와 분리 유지)
# strip() — Render UI 등 다단행 텍스트 영역에서 줄바꿈 들어가는 케이스 방어.
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://fridgechef:fridgechef@localhost:5432/fridgechef",
).strip()

# sqlite는 pool 인자를 지원 안 함 → 드라이버 분기 (테스트 환경 호환)
_engine_kwargs: dict = {"echo": False}
if not DATABASE_URL.startswith("sqlite"):
    # NFR-OPS-002: Postgres 운영 풀
    _engine_kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True})

# Supabase pooler 호환: SSL 강제 + self-signed 검증 우회 + statement cache 비활성.
# - macOS+anaconda 인증서 체인 + Render 컨테이너 모두 동일 문제 → 한 곳에서 처리.
# - pooler(6543) 는 prepared statement 충돌 방지 위해 statement_cache_size=0 필수.
if "pooler.supabase.com" in DATABASE_URL or "supabase.co" in DATABASE_URL:
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE
    _engine_kwargs["connect_args"] = {
        "ssl": _ssl_ctx,
        "statement_cache_size": 0,
    }

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    """SQLAlchemy 선언적 베이스 — 모든 ORM 모델의 부모."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI DI 용 세션 생성기."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
