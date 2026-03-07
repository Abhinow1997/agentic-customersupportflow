# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ────────────────────────────────────────────────────────────────
    APP_NAME: str = "Arcella Support API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"

    # ── Snowflake ──────────────────────────────────────────────────────────
    SNOWFLAKE_ACCOUNT: str
    SNOWFLAKE_USERNAME: str
    SNOWFLAKE_PASSWORD: str
    SNOWFLAKE_DATABASE: str
    SNOWFLAKE_SCHEMA: str
    SNOWFLAKE_WAREHOUSE: str
    SNOWFLAKE_ROLE: str

    # ── LLM ───────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""

    # ── ChromaDB (RAG) ─────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./chroma_walmart_policies"
    CHROMA_COLLECTION: str = "walmart_policies"

    # ── CORS ───────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",   # SvelteKit dev
        "http://localhost:4173",   # SvelteKit preview
        "http://localhost:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
