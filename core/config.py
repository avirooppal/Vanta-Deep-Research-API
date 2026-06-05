from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    environment: str = "development"
    max_research_rounds: int = 3
    extraction_concurrency: int = 3
    webhook_max_retries: int = 5
    audit_retention_days: int = 365
    export_cache_ttl_seconds: int = 86400

    class Config:
        env_file = ".env"


settings = Settings()
