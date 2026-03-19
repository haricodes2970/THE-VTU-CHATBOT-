"""
backend/core/config.py
Central configuration — all settings loaded from environment variables.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────
    app_name: str = "VTU Smart Scheduler"
    app_env: str = "development"
    app_port: int = 8000
    secret_key: str = "change-me"

    # ── Database ─────────────────────────────────────────────
    database_url: str = "postgresql://vtu_user:vtu_password@localhost:5432/vtu_scheduler"

    # ── Groq ─────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama3-8b-8192"

    # ── Pinecone ─────────────────────────────────────────────
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1-aws"
    pinecone_index_name: str = "vtu-circulars"
    pinecone_dimension: int = 384

    # ── VTU Scraper ───────────────────────────────────────────
    vtu_base_url: str = "https://vtu.ac.in"
    vtu_circulars_url: str = "https://vtu.ac.in/circulars"
    scraper_interval_hours: int = 6
    pdf_download_path: str = "./data/pdfs"

    # ── Email ────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""

    # ── Telegram ─────────────────────────────────────────────
    telegram_bot_token: str = ""

    # ── Redis ────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance (call this everywhere)."""
    return Settings()


settings = get_settings()
