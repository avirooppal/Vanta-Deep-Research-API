import uuid
import json
import asyncio
import httpx
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from db.session import get_db_session
from db.models.research_job import ResearchJob
from db.models.report import Report
from db.models.source import Source
from db.models.llm_backend import LLMBackend
from db.models.usage_record import UsageRecord
from db.models.api_key import APIKey
from db.models.org import Org
from core.llm.client import LLMClient
from core.research.engine import run_research, RoundResult
from core.config import settings
from core.webhooks.dispatcher import fire_webhook
from arq import create_pool

logger = logging.getLogger(__name__)


async def run_research_job(ctx: dict, job_id: str) -> None:
    cancel_event = asyncio.Event()
    llm = None

    async def on_progress(result: RoundResult) -> None:
        async with get_db_session() as db:
            job_row = await db.get(ResearchJob, job_id)
            if job_row and job_row.status == "cancelled":
                cancel_event.set()
                return

            for finding in result.new_findings:
                db.add(Source(
                    id=f"src_{uuid.uuid4().hex[:12]}",
                    job_id=job_id,
                    org_id=job_row.org_id,
                    url=finding.url,
                    title=finding.title,
                    excerpt=finding.facts[:500],
                    round_number=finding.round_number,
                ))
            await db.commit()

    try:
        async with get_db_session() as db:
            job = await db.get(ResearchJob, job_id)
            if not job or job.status == "cancelled":
                return
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)

            # Check if transient backend details are specified
            if job.metadata_json:
                try:
                    meta = json.loads(job.metadata_json)
                    tb = meta.get("transient_backend")
                    if tb:
                        from core.security.encryption import decrypt
                        from core.llm.types import LLMConfig
                        enc_key = tb.get("api_key_encrypted")
                        if enc_key:
                            if isinstance(enc_key, str):
                                enc_key = enc_key.encode("utf-8")
                            api_key = decrypt(enc_key)
                        else:
                            api_key = None

                        config = LLMConfig(
                            provider=tb.get("provider", "openai"),
                            base_url=tb.get("base_url", "https://api.openai.com/v1"),
                            api_key=api_key,
                            model=tb.get("model", "gpt-4o"),
                            max_concurrent=3
                        )
                        llm = LLMClient(config)
                except Exception as e:
                    logger.error(f"Failed to load transient backend: {e}")

            if not llm:
                backend_result = await db.execute(
                    select(LLMBackend).where(
                        LLMBackend.org_id == job.org_id,
                        LLMBackend.is_default == True,
                    )
                )
                backend = backend_result.scalar_one_or_none()
                if not backend:
                    job.status = "failed"
                    job.error = "No default LLM backend configured for this organisation"
                    job.finished_at = datetime.now(timezone.utc)
                    raise ValueError("No default LLM backend configured for this organisation")

                llm = LLMClient.from_backend(backend)

            llm.total_tokens_in = 0
            llm.total_tokens_out = 0
            llm.search_queries_issued = 0
            llm.sources_fetched = 0


        report_output = await run_research(
            question=job.query,
            llm=llm,
            searxng_url=settings.searxng_url,
            max_rounds=job.max_rounds,
            on_progress=on_progress,
            cancelled=cancel_event,
        )

        async with get_db_session() as db:
            report = Report(
                id=f"rpt_{uuid.uuid4().hex[:12]}",
                job_id=job_id,
                org_id=job.org_id,
                summary=report_output.summary,
                content_md=report_output.body_md,
                content_json=json.dumps({"citations": report_output.citations}),
            )
            db.add(report)

            # Sources are now inserted incrementally during on_progress

            job_row = await db.get(ResearchJob, job_id)
            job_row.status = "completed"
            job_row.finished_at = datetime.now(timezone.utc)

            duration = int((job_row.finished_at - job_row.started_at).total_seconds()) if job_row.started_at else 0
            usage = UsageRecord(
                id=f"usg_{uuid.uuid4().hex[:12]}",
                job_id=job_id,
                org_id=job_row.org_id,
                tokens_in=llm.total_tokens_in,
                tokens_out=llm.total_tokens_out,
                sources_fetched=llm.sources_fetched,
                search_queries_issued=llm.search_queries_issued,
                duration_seconds=duration,
                created_at=datetime.now(timezone.utc),
            )
            db.add(usage)

        await fire_webhook(job_id, "research.completed")

    except Exception as exc:
        async with get_db_session() as db:
            job_row = await db.get(ResearchJob, job_id)
            if job_row:
                job_row.status = "failed"
                job_row.error = str(exc)[:1000]
                job_row.finished_at = datetime.now(timezone.utc)

                if llm:
                    duration = int((job_row.finished_at - job_row.started_at).total_seconds()) if job_row.started_at else 0
                    usage = UsageRecord(
                        id=f"usg_{uuid.uuid4().hex[:12]}",
                        job_id=job_id,
                        org_id=job_row.org_id,
                        tokens_in=llm.total_tokens_in,
                        tokens_out=llm.total_tokens_out,
                        sources_fetched=llm.sources_fetched,
                        search_queries_issued=llm.search_queries_issued,
                        duration_seconds=duration,
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(usage)

        await fire_webhook(job_id, "research.failed")


async def deliver_webhook_job(ctx: dict, url: str, payload: str, signature: str, attempt: int = 1) -> None:
    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
        "User-Agent": "DeepResearchWebhook/1.0"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, content=payload, headers=headers)
            r.raise_for_status()
            logger.info(f"Webhook delivered successfully to {url}")
    except Exception as exc:
        logger.warning(f"Webhook delivery failed to {url} (attempt {attempt}/5): {exc}")
        if attempt < 5:
            backoffs = [10, 30, 120, 600]
            delay = backoffs[attempt - 1] if attempt - 1 < len(backoffs) else 3600

            from core.queue.worker import get_redis_settings
            redis = await create_pool(get_redis_settings())
            await redis.enqueue_job(
                "deliver_webhook_job",
                url=url,
                payload=payload,
                signature=signature,
                attempt=attempt + 1,
                _defer_by=delay
            )
            await redis.aclose()
        else:
            logger.error(f"Webhook delivery permanently failed to {url} after 5 attempts.")
