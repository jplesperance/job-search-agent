from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://job_agent:job_agent@localhost:5432/job_agent"
    openai_api_key: str | None = None
    log_level: str = "INFO"

    scheduled_discovery_minimum_score: float = 80.0
    notification_provider: str = "disabled"
    notification_recipient: str | None = None
    notification_max_attempts: int = 3
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
