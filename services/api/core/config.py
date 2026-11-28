"""Application configuration for Multiverse API & Worker."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_base_url: str = "http://localhost:5173"
    api_host: str = "0.0.0.0"
    api_port: int = 8001

    session_secret: str = "dev-session-secret-change-in-production"
    auth_secret: str = "dev-auth-secret-change-in-production"
    credential_encryption_key: str = ""

    firebase_project_id: str = ""
    firebase_service_account_path: str = ""

    database_url: str = f"sqlite:///{(ROOT_DIR / 'data' / 'multiverse.db').as_posix()}"
    redis_url: str = "redis://localhost:6379/0"

    flagsmith_api_url: str = "http://localhost:8000/api/v1/"
    flagsmith_management_api_token: str = ""
    flagsmith_shop_env_key: str = ""
    flagsmith_learning_env_key: str = ""
    flagsmith_workspace_env_key: str = ""

    passport_private_key_path: str = str(ROOT_DIR / "infra" / "keys" / "passport_ed25519.pem")
    passport_public_key_path: str = str(ROOT_DIR / "infra" / "keys" / "passport_ed25519.pub.pem")
    passport_issuer: str = "multiverse"
    passport_key_id: str = "multiverse-key-01"

    exploration_max_concurrency: int = 2
    exploration_default_budget: int = 64
    exploration_timeout_seconds: int = 120
    artifact_storage_path: str = str(ROOT_DIR / "data" / "artifacts")

    allowed_exploration_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://web:5173"
    allowed_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    allowed_cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?::\d+)?$"

    # Tinker (Thinking Machines Lab) OpenAI-compatible inference. The API key
    # stays server-side and is never returned to the dashboard.
    tinker_api_key: str = ""
    tinker_base_url: str = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1"
    tinker_model: str = "thinkingmachines/Inkling:peft:262144"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_exploration_origins.split(",") if o.strip()]

    @property
    def allowed_cors_origins_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    Path(settings.artifact_storage_path).mkdir(parents=True, exist_ok=True)
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.replace("sqlite:///", ""))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
