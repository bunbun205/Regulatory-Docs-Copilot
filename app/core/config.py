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
    MAX_UPLOAD_BYTES: int = Field(default=25 * 1024 * 1024, ge=1)
    MAX_REQUEST_BYTES: int = Field(default=26 * 1024 * 1024, ge=1)
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
    LLM_REASONING_EFFORT: Literal["none", "minimal", "low", "medium", "high"] | None = None

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

    GAPCHECK_MAX_CLAUSES: int = Field(default=80, ge=1, le=500)
    GAPCHECK_MAX_REQUIREMENTS: int = Field(default=120, ge=1, le=500)
    GAPCHECK_MAX_TOKENS: int = Field(default=200_000, ge=1000)
    GAPCHECK_MAX_SOP_CHARS: int = Field(default=200_000, ge=1000)
    GAPCHECK_RETRIEVAL_TOP_K: int = Field(default=5, ge=1, le=20)
    GAPCHECK_RELEVANCE_THRESHOLD: float = Field(default=0.60, ge=0.0, le=1.0)
    GAPCHECK_GLOBAL_TOP_DOCUMENTS: int = Field(default=2, ge=1, le=10)
    GAPCHECK_SOP_MATCH_TOP_K: int = Field(default=3, ge=1, le=10)
    GAPCHECK_JUDGE_CONCURRENCY: int = Field(default=4, ge=1, le=10)
    GAPCHECK_RETRIEVAL_CONCURRENCY: int = Field(default=8, ge=1, le=20)
    GAPCHECK_JUDGE_MAX_TOKENS: int = Field(default=512, ge=64, le=4096)
    GAPCHECK_MAX_CONCURRENT_JOBS_PER_KEY: int = Field(default=1, ge=1, le=1)
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, ge=1)
    RATE_LIMIT_MAX_IDENTITIES: int = Field(default=10_000, ge=1)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
