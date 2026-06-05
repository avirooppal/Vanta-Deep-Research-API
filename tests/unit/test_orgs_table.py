import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from core.config import settings


@pytest.mark.asyncio
async def test_orgs_table_exists():
    eng = create_async_engine(settings.database_url)
    try:
        async with eng.connect() as conn:
            r = await conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_name='orgs'")
            )
            assert r.scalar() == "orgs", "orgs table not found"
    finally:
        await eng.dispose()
