import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from core.config import settings

EXPECTED_TABLES = [
    "orgs",
    "api_keys",
    "research_jobs",
    "reports",
    "sources",
    "audit_log",
    "usage_records",
    "llm_backends",
]


@pytest.mark.asyncio
async def test_all_tables_exist():
    eng = create_async_engine(settings.database_url)
    try:
        async with eng.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            )
            existing = {row[0] for row in result.fetchall()}
    finally:
        await eng.dispose()

    for table in EXPECTED_TABLES:
        assert table in existing, f"Missing table: {table}"
