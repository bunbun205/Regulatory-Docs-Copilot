from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_prefix="LABDOCS_",
        env_file=".env",
        extra="ignore",
    )

    APP_NAME: str = "labdocs"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"
    DATABASE_URL: str = "postgresql+asyncpg://labdocs:labdocs@localhost:5432/labdocs"

    UPLOAD_DIR: Path = Path("data/uploads")
    MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024
    CHUNK_MAX_TOKENS: int = 500
    CHUNK_OVERLAP_TOKENS: int = 80

    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 32

    VECTOR_BACKEND: Literal["pgvector", "qdrant", "both"] = "pgvector"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "labdocs_chunks"
    QDRANT_API_KEY: str | None = None
    QDRANT_TIMEOUT_SECONDS: int = 10

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
