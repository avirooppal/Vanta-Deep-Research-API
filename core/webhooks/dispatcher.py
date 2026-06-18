import json
import logging
from sqlalchemy import select
from db.session import get_db_session
from db.models.webhook import WebhookEndpoint
from db.models.research_job import ResearchJob
from core.webhooks.signing import hmac_sign
from arq import create_pool


logger = logging.getLogger(__name__)


async def fire_webhook(job_id: str, event_type: str) -> None:
    async with get_db_session() as db:
        job = await db.get(ResearchJob, job_id)
        if not job:
            return

        # Get all active webhooks
        stmt = select(WebhookEndpoint).where(
            WebhookEndpoint.is_active
        )
        result = await db.execute(stmt)
        endpoints = result.scalars().all()

        if not endpoints:
            return

        payload_dict = {
            "event": event_type,
            "job_id": job.id,
            "status": job.status,
            "query": job.query,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        }

        # If job has report, include report_url
        from db.models.report import Report
        stmt_report = select(Report).where(Report.job_id == job.id)
        result_report = await db.execute(stmt_report)
        report = result_report.scalar_one_or_none()
        if report:
            payload_dict["report_url"] = f"/v1/reports/{report.id}"
        elif job.error:
            payload_dict["error"] = job.error

        payload_str = json.dumps(payload_dict)

        from core.queue.worker import get_redis_settings
        redis = await create_pool(get_redis_settings())

        from core.security.encryption import decrypt
        import time
        timestamp = str(int(time.time()))
        for ep in endpoints:
            decrypted_secret = decrypt(ep.secret)
            sig = f"t={timestamp},v1={hmac_sign(payload_str, timestamp, decrypted_secret)}"
            await redis.enqueue_job(
                "deliver_webhook_job",
                url=ep.url,
                payload=payload_str,
                signature=sig,
                timestamp=timestamp,
                attempt=1,
                _job_id=f"webhook_{job_id}_{ep.id}"
            )
        await redis.aclose()
