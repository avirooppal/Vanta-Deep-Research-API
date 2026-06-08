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
from db.models.source import Source
from arq import create_pool
from core.queue.worker import get_redis_settings
from core.llm.client import LLMClient
from core.llm.types import LLMConfig, Message as LLMMessage
router = APIRouter(prefix="/v1", tags=["research"])


class ResearchRequest(BaseModel):
    query: str
    max_rounds: int = 3
    priority: int = 3
    model_override: Optional[str] = None
    metadata: Optional[dict] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class ResearchResponse(BaseModel):
    id: str
    status: str
    query: str
    created_at: str


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


@router.post("/research", response_model=ResearchResponse, status_code=202)
async def submit_research(body: ResearchRequest, request: Request):
    org_id = request.state.org_id
    api_key_id = request.state.api_key_id

    job_id = f"job_{uuid.uuid4().hex[:12]}"

    transient_backend = getattr(request.state, "transient_backend", None)

    final_backend = transient_backend.copy() if transient_backend else {}
    if body.provider:
        final_backend["provider"] = body.provider
    if body.api_key:
        final_backend["api_key"] = body.api_key
    if body.base_url:
        final_backend["base_url"] = body.base_url
    if body.model:
        final_backend["model"] = body.model

    metadata = body.metadata or {}
    if final_backend:
        if "api_key" in final_backend and final_backend["api_key"]:
            from core.security.encryption import encrypt
            final_backend["api_key_encrypted"] = encrypt(final_backend["api_key"]).decode("utf-8")
            final_backend.pop("api_key", None)
        metadata["transient_backend"] = final_backend

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
            metadata_json=json.dumps(metadata) if metadata else None,
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

    if job.status in ("running", "completed"):
        async with get_db_session() as db:
            sources_result = await db.execute(select(Source).where(Source.job_id == job_id))
            sources = sources_result.scalars().all()
            
            partial_sources = []
            max_round = 0
            for s in sources:
                partial_sources.append({
                    "url": s.url,
                    "title": s.title,
                    "excerpt": s.excerpt,
                    "round_number": s.round_number
                })
                if s.round_number > max_round:
                    max_round = s.round_number
            
            response_data["partial_sources"] = partial_sources
            response_data["rounds_completed"] = max_round

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

@router.post("/research/{job_id}/chat")
async def chat_with_report(job_id: str, body: ChatRequest, request: Request):
    org_id = request.state.org_id

    async with get_db_session() as db:
        job = await db.get(ResearchJob, job_id)
        if not job or job.org_id != org_id:
            raise HTTPException(status_code=404, detail="Job not found")
            
        result = await db.execute(select(Report).where(Report.job_id == job_id))
        report = result.scalar_one_or_none()
        
    if not report:
        raise HTTPException(status_code=404, detail="Report not yet generated for this job")

    transient_backend = getattr(request.state, "transient_backend", None)
    final_backend = transient_backend.copy() if transient_backend else {}
    if body.provider:
        final_backend["provider"] = body.provider
    if body.api_key:
        final_backend["api_key"] = body.api_key
    if body.base_url:
        final_backend["base_url"] = body.base_url
    if body.model:
        final_backend["model"] = body.model

    if not final_backend:
        raise HTTPException(status_code=401, detail="No LLM backend configuration found")

    config = LLMConfig(
        provider=final_backend.get("provider", "openai"),
        api_key=final_backend.get("api_key"),
        base_url=final_backend.get("base_url"),
        model=final_backend.get("model", "gpt-4o"),
        temperature=0.7
    )
    llm = LLMClient(config)

    system_prompt = (
        "[Research context — 2026-06-08]\n"
        "The user previously ran a deep research investigation. "
        "Use the report below as your primary knowledge base when answering follow-up questions. "
        "If the user asks something not covered, say so plainly rather than guessing.\n\n"
        "=== ORIGINAL QUERY ===\n" + job.query + "\n\n"
        "=== REPORT ===\n" + report.content_md
    )

    messages = [LLMMessage(role="system", content=system_prompt)]
    for msg in body.history:
        messages.append(LLMMessage(role=msg.role, content=msg.content))
    messages.append(LLMMessage(role="user", content=body.message))

    llm_response = await llm.complete(messages)

    return {"response": llm_response.content}
