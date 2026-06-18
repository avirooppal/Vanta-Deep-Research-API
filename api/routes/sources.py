import base64
import json
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Query
from sqlalchemy import select
from db.session import get_db_session
from db.models.source import Source
from db.models.research_job import ResearchJob

router = APIRouter(prefix="/v1", tags=["sources"])


@router.get("/research/{job_id}/sources")
async def get_research_sources(
    job_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = None
):
    async with get_db_session() as db:
        # Check that job exists
        job = await db.get(ResearchJob, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        stmt = select(Source).where(Source.job_id == job_id)

        if cursor:
            try:
                decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
                cursor_data = json.loads(decoded)
                cursor_fetched_at = datetime.fromisoformat(cursor_data["fetched_at"])
                cursor_id = cursor_data["id"]
                
                stmt = stmt.where(
                    (Source.fetched_at < cursor_fetched_at) |
                    ((Source.fetched_at == cursor_fetched_at) & (Source.id < cursor_id))
                )
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid cursor format")

        stmt = stmt.order_by(Source.fetched_at.desc(), Source.id.desc()).limit(limit + 1)
        result = await db.execute(stmt)
        sources = result.scalars().all()

        has_more = len(sources) > limit
        if has_more:
            sources = sources[:limit]

        next_cursor = None
        if sources:
            last_source = sources[-1]
            cursor_data = {
                "fetched_at": last_source.fetched_at.isoformat(),
                "id": last_source.id
            }
            next_cursor = base64.urlsafe_b64encode(json.dumps(cursor_data).encode()).decode()

    items = [
        {
            "id": src.id,
            "url": src.url,
            "title": src.title,
            "excerpt": src.excerpt,
            "round_number": src.round_number,
            "fetched_at": src.fetched_at.isoformat() if src.fetched_at else None
        }
        for src in sources
    ]

    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more
    }
