import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from core.config import settings


@pytest.mark.asyncio
async def test_db_connects():
    eng = create_async_engine(settings.database_url)
    try:
        async with eng.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
    finally:
        await eng.dispose()
