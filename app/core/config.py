from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://billing:billing@localhost:5432/billing"
    app_env: str = "development"
    log_level: str = "INFO"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""
    checkout_success_url: str = "http://localhost:8000/docs"
    checkout_cancel_url: str = "http://localhost:8000/docs"
    demo_tenant_a_api_key: str = "demo_tenant_a_key"
    demo_tenant_b_api_key: str = "demo_tenant_b_key"
    worker_poll_seconds: int = 10
    worker_max_attempts: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
