from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
from db.session import get_db_session
from db.models.source import Source
from db.models.research_job import ResearchJob

router = APIRouter(prefix="/v1", tags=["sources"])


@router.get("/research/{job_id}/sources")
async def get_research_sources(job_id: str, request: Request):
    org_id = request.state.org_id

    async with get_db_session() as db:
        # Check that job exists and belongs to the org
        job = await db.get(ResearchJob, job_id)
        if not job or job.org_id != org_id:
            raise HTTPException(status_code=404, detail="Job not found")

        stmt = select(Source).where(Source.job_id == job_id)
        result = await db.execute(stmt)
        sources = result.scalars().all()

    return [
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
