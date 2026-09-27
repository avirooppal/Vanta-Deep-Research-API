from pydantic_settings import BaseSettings


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

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
