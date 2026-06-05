import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Import Base and all models for autogenerate
from db.engine import Base
from db.models.org import Org  # noqa: F401
from db.models.api_key import APIKey  # noqa: F401
from db.models.research_job import ResearchJob  # noqa: F401
from db.models.report import Report  # noqa: F401
from db.models.source import Source  # noqa: F401
from db.models.audit_log import AuditLog  # noqa: F401
from db.models.usage_record import UsageRecord  # noqa: F401
from db.models.llm_backend import LLMBackend  # noqa: F401

# Alembic Config object
config = context.config

# Set DB URL from our settings (overrides alembic.ini)
from core.config import settings
config.set_main_option("sqlalchemy.url", settings.database_url)

# Logging setup
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
