from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def build_engine(
    database_url: str,
    *,
    echo: bool = False,
    pooled: bool = True,
) -> AsyncEngine:
    engine_options: dict[str, object] = {
        "echo": echo,
        "pool_pre_ping": True,
    }
    if not pooled:
        engine_options["poolclass"] = NullPool
    return create_async_engine(database_url, **engine_options)


def build_session_factory(
    database_url: str,
    *,
    echo: bool = False,
    pooled: bool = True,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        build_engine(database_url, echo=echo, pooled=pooled),
        expire_on_commit=False,
    )


async def session_scope(
    sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with sessions() as session:
        yield session


def _upgrade(database_url: str) -> None:
    repository_root = Path(__file__).resolve().parents[5]
    config = Config(str(repository_root / "services" / "backend" / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


async def run_migrations(database_url: str) -> None:
    await asyncio.to_thread(_upgrade, database_url)
