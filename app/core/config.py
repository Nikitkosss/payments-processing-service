from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "payments-service"

    api_key: str
    database_url: str
    rabbit_url: str

    outbox_poll_interval: float = 1.0
    outbox_batch_size: int = 100

    webhook_timeout: float = 10.0
    max_delivery_attempts: int = 3

    log_level: str = "INFO"
    log_json: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
