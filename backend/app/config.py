"""
Application configuration — Pydantic Settings.

Mirrors InsureFlow's config.py conventions:
- Reads from environment variables (.env in local dev, docker-compose in containers)
- Safe defaults embedded (zero host dependencies needed for evaluation)
- Postgres-primary with SQLite fallback for tests / standalone execution
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "LeadFlow — Lead Intelligence & Opportunity Platform"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = True
    backend_host: str = "0.0.0.0"
    backend_port: int = 8002
    frontend_port: int = 3001
    log_level: str = "INFO"

    # --- Database (Postgres primary, SQLite fallback for tests) ---
    database_url: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5435/leadflow",
        description="SQLAlchemy 2.0 URL (psycopg2 driver)",
    )
    sqlite_fallback_url: str = "sqlite:///./leadflow.db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # --- Auth ---
    jwt_secret: str = "change-me-in-real-deploy-32-chars-min"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # --- Data generator (per InsureFlow: seed 20261022) ---
    data_gen_seed: int = 20261022
    auto_seed_on_startup: bool = True
    data_gen_mode: Literal["starter", "full"] = "full"

    # --- Scoring thresholds (A5) ---
    score_version: str = "v1"
    score_hot_threshold: int = 80
    score_warm_threshold: int = 60
    score_nurture_threshold: int = 40

    # --- Frontend ---
    vite_api_base_url: str = "http://localhost:8000/api"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
