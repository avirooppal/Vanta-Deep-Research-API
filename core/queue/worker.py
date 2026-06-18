from urllib.parse import urlparse
from arq.connections import RedisSettings
from arq.cron import cron
from core.queue.tasks import run_research_job, deliver_webhook_job, cleanup_audit_log
from core.config import settings


def get_redis_settings() -> RedisSettings:
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )


class WorkerSettings:
    functions = [run_research_job, deliver_webhook_job]
    cron_jobs = [cron(cleanup_audit_log, hour=3, minute=0)]
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 1800         # 30 minutes max per research job
    keep_result = 3600         # Keep results in Redis for 1 hour


