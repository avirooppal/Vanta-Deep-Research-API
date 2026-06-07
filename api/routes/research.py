import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from db.session import get_db_session
from db.models.research_job import ResearchJob
from db.models.report import Report
from arq import create_pool
from core.queue.worker import get_redis_settings

router = APIRouter(prefix="/v1", tags=["research"])


class ResearchRequest(BaseModel):
    query: str
    max_rounds: int = 3
    priority: int = 3
    model_override: Optional[str] = None
    metadata: Optional[dict] = None


class ResearchResponse(BaseModel):
    id: str
    status: str
    query: str
    created_at: str


@router.post("/research", response_model=ResearchResponse, status_code=202)
async def submit_research(body: ResearchRequest, request: Request):
    org_id = request.state.org_id
    api_key_id = request.state.api_key_id

    job_id = f"job_{uuid.uuid4().hex[:12]}"

    async with get_db_session() as db:
        job = ResearchJob(
            id=job_id,
            org_id=org_id,
            api_key_id=api_key_id,
            query=body.query,
            status="queued",
            max_rounds=min(body.max_rounds, 5),
            priority=max(1, min(5, body.priority)),
            model_override=body.model_override,
            metadata_json=json.dumps(body.metadata) if body.metadata else None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(job)

    request.state.query_text = body.query

    redis = await create_pool(get_redis_settings())
    await redis.enqueue_job("run_research_job", job_id, _job_id=job_id)
    await redis.aclose()

    return ResearchResponse(
        id=job_id,
        status="queued",
        query=body.query,
        created_at=job.created_at.isoformat(),
    )


@router.get("/research/{job_id}")
async def get_research_job(job_id: str, request: Request):
    org_id = request.state.org_id

    async with get_db_session() as db:
        job = await db.get(ResearchJob, job_id)

    if not job or job.org_id != org_id:
        raise HTTPException(status_code=404, detail="Job not found")

    response_data = {
        "id": job.id,
        "status": job.status,
        "query": job.query,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error": job.error,
    }

    if job.status == "completed":
        async with get_db_session() as db:
            result = await db.execute(select(Report).where(Report.job_id == job_id))
            report = result.scalar_one_or_none()

        if report:
            content_json = json.loads(report.content_json) if report.content_json else {}
            response_data["report"] = {
                "id": report.id,
                "summary": report.summary,
                "body_md": report.content_md,
                "citations": content_json.get("citations", []),
            }

    return response_data


@router.delete("/research/{job_id}", status_code=204)
async def cancel_research_job(job_id: str, request: Request):
    org_id = request.state.org_id

    async with get_db_session() as db:
        job = await db.get(ResearchJob, job_id)

        if not job or job.org_id != org_id:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status in ("completed", "failed", "cancelled"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot cancel job with status: {job.status}"
            )

        job.status = "cancelled"
        job.finished_at = datetime.now(timezone.utc)
