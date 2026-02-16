from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AI
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o", description="OpenAI model ID")
    fast_model: str = Field(default="gpt-4o-mini", description="Fast/cheap model for routing")
    strong_model: str = Field(default="gpt-4o", description="Strong model for complex tasks")

    # Tavily (web search)
    tavily_api_key: str | None = Field(default=None, description="Tavily API key for web search")

    # External services
    rapidapi_key: str | None = Field(default=None, description="RapidAPI key for JSearch")

    # PostgreSQL (for LangGraph checkpointer + app tables)
    postgres_url: str = Field(
        default="postgresql://localhost:5432/jobflow",
        description="PostgreSQL connection URL",
        validation_alias=AliasChoices("postgres_url", "database_url"),
    )

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8002)
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # Resume storage
    resume_dir: str = Field(default="data/resumes")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
