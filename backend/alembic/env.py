"""Alembic 환경 (SDD §1.3 데이터 마이그레이션)."""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.db import Base

# 모델 import 로 메타데이터 등록
from app.models import orm  # noqa: F401

config = context.config

# DATABASE_URL 환경변수가 있으면 동기 드라이버로 변환해서 주입
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option(
        "sqlalchemy.url",
        db_url.replace("+asyncpg", "+psycopg2"),
    )

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
