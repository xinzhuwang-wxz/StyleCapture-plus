from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from stylecapture_backend.features.capture.infrastructure.models import (
    CaptureRecord,
    ProcessingJobRecord,
)
from stylecapture_backend.features.look.infrastructure.models import (
    LookComponentRecord,
    LookRecord,
    PreferenceSignalRecord,
)
from stylecapture_backend.features.outfit.infrastructure.models import (
    OutfitWorkflowTraceRecord,
    PurchaseDemandRecord,
)
from stylecapture_backend.features.render.infrastructure.models import RenderArtifactRecord
from stylecapture_backend.features.wardrobe.infrastructure.models import ItemRecord
from stylecapture_backend.platform.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
_MODELS = (
    CaptureRecord,
    ProcessingJobRecord,
    ItemRecord,
    LookRecord,
    LookComponentRecord,
    PreferenceSignalRecord,
    PurchaseDemandRecord,
    OutfitWorkflowTraceRecord,
    RenderArtifactRecord,
)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
