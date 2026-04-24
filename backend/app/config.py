from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Walmart Support API"
    APP_VERSION: str = "0.1.1"
    APP_ENV: str = "development"

    SNOWFLAKE_ACCOUNT: str
    SNOWFLAKE_USERNAME: str
    SNOWFLAKE_PASSWORD: str
    SNOWFLAKE_DATABASE: str
    SNOWFLAKE_SCHEMA: str
    SNOWFLAKE_WAREHOUSE: str
    SNOWFLAKE_ROLE: str

    OPENAI_API_KEY: str = ""

    IMAGE_MODEL: str = "gpt-image-2"
    IMAGE_SIZE: str = "512x512"

    CHROMA_PERSIST_DIR: str = "./chroma_walmart_policies"
    CHROMA_COLLECTION: str = "walmart_policies"

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:4173,http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Convert comma-separated CORS_ORIGINS string to list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()