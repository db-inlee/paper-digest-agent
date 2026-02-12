"""Configuration module using pydantic-settings."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    slack_webhook_url: str = ""
    slack_signing_secret: str = ""
    slack_bot_token: str = ""
    report_base_dir: Path = Path("../reports")
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    allowed_origins: str = ""  # 쉼표 구분, 예: "https://paper.example.com"

    # LLM (for keyword extraction) — falls back to OPENAI_API_KEY
    llm_api_key: str = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    llm_base_url: str = "https://api.openai.com/v1/chat/completions"
    llm_model: str = "gpt-4o-mini"

    # Web build directory (set in Docker; empty = auto-detect from source tree)
    web_build_dir: str = ""

    # Scheduler
    scheduler_enabled: bool = False
    scheduler_cron_hour: int = 9
    scheduler_cron_minute: int = 0
    scheduler_timezone: str = "Asia/Seoul"

    @property
    def daily_reports_dir(self) -> Path:
        """Return the daily reports directory path."""
        return self.report_base_dir / "daily"


settings = Settings()
