from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://cie:cie@localhost:5432/cie"
    database_url_sync: str = "postgresql+psycopg2://cie:cie@localhost:5432/cie"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API auth
    api_key: str = "changeme-dev-key"
    cors_origins: str = "http://localhost:3000"

    # Anthropic
    anthropic_api_key: str = ""

    # Voyage AI (embeddings, primary)
    voyage_api_key: str = ""

    # OpenAI (embeddings fallback)
    openai_api_key: str = ""

    # External APIs
    news_api_key: str = ""
    github_token: str = ""

    # LLM limits
    max_llm_calls_per_run: int = 50
    max_llm_calls_per_day: int = 200

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
