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

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
