from pathlib import Path
from typing import Literal

from pydantic import Field
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

    LLM_PROVIDER: Literal["fake", "openai_compatible", "anthropic", "azure_openai"] = (
        "openai_compatible"
    )
    LLM_MODEL: str = "qwen2.5:7b"
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: str | None = None
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_MAX_RETRIES: int = 2
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_TOKENS: int = 1024

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ANTHROPIC_VERSION: str = "2023-06-01"

    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_DEPLOYMENT: str | None = None
    AZURE_OPENAI_API_VERSION: str = "2024-10-21"

    RAG_TOP_K: int = 8
    ABSTENTION_THRESHOLD: float = 0.75

    AGENT_MAX_STEPS: int = Field(default=5, ge=1, le=5)
    AGENT_STEP_TIMEOUT_SECONDS: float = Field(default=20.0, gt=0)
    AGENT_TOTAL_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0)
    AGENT_MAX_TOOL_OUTPUT_CHARS: int = Field(default=8000, ge=500)
    AGENT_MAX_METADATA_ROWS: int = Field(default=50, ge=1, le=100)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
