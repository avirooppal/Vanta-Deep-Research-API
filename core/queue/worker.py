from urllib.parse import urlparse
from arq.connections import RedisSettings
from core.queue.tasks import run_research_job, deliver_webhook_job
from core.config import settings


def get_redis_settings() -> RedisSettings:
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
    )


class WorkerSettings:
    functions = [run_research_job, deliver_webhook_job]
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 600          # 10 minutes max per research job
    keep_result = 3600         # Keep results in Redis for 1 hour

