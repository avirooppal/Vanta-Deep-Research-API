from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    environment: str = "development"
    max_research_rounds: int = 3
    extraction_concurrency: int = 3
    searxng_url: str = "http://searxng:8080"
    webhook_max_retries: int = 5
    audit_retention_days: int = 365
    export_cache_ttl_seconds: int = 86400

    # LLM Gateway — rate limiting
    llm_gateway_max_retries: int = 4
    llm_cred_max_rpm: int = 0          # 0 = unlimited (set per-key)
    llm_cred_max_tpm: int = 0
    llm_cred_max_concurrent: int = 2
    llm_provider_max_concurrent: int = 16

    # LLM Gateway — circuit breaker
    llm_cb_failure_threshold: int = 5
    llm_cb_half_open_after_s: float = 60.0

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Normalize cloud provider database URLs (postgres://, postgresql://) to asyncpg driver."""
        if isinstance(v, str):
            v = v.strip()
            # Clean up accidental spaces like postgres: password@...
            v = v.replace("postgres: ", "postgres:").replace("postgresql: ", "postgresql:")
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("redis_url", mode="before")
    @classmethod
    def normalize_redis_url(cls, v: str) -> str:
        """Ensure TLS (rediss://) for cloud Redis providers like Upstash."""
        if isinstance(v, str):
            v = v.strip()
            # Upstash requires TLS on port 6379
            if "upstash.io" in v and v.startswith("redis://"):
                v = v.replace("redis://", "rediss://", 1)
        return v

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
