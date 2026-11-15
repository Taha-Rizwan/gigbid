"""Runtime settings. Secrets come only from environment variables (.env locally)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    app_env: str = "development"
    app_secret_key: str = "dev-only-change-me"
    token_encryption_key: str | None = None  # Fernet key for OAuth tokens
    database_url: str | None = None  # postgres; falls back to local sqlite in dev/tests
    redis_url: str | None = None
    cors_origins: list[str] = ["http://localhost:3000"]
    public_base_url: str = "http://localhost:3000"

    marketplace_mode: str | None = None  # overrides agent/config.yaml when set
    gigsim_base_url: str = "http://localhost:8081"
    mcp_marketplace_url: str = "http://localhost:8101/mcp"
    mcp_portfolio_url: str = "http://localhost:8102/mcp"
    mcp_workspace_url: str = "http://localhost:8103/mcp"
    mcp_auth_token: str = "dev-mcp-token"

    groq_api_key: str | None = None
    openai_api_key: str | None = None
    langsmith_api_key: str | None = None
    langsmith_project: str = "gigbid"
    github_token: str | None = None
    github_repo_url: str | None = None

    upwork_mcp_url: str = "https://mcp.upwork.com/mcp"
    upwork_client_id: str | None = None
    upwork_client_secret: str | None = None

    reviewer_email: str = "reviewer@gigbid.dev"
    reviewer_password: str | None = None

    @property
    def sqlite_path(self) -> Path:
        return ROOT / "data" / "cache" / "gigbid.sqlite"


settings = Settings()

# LangSmith tracing is on whenever a key is configured (every graph run becomes a trace).
if settings.langsmith_api_key:
    import os as _os

    _os.environ.setdefault("LANGSMITH_TRACING", "true")
    _os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    _os.environ.setdefault("LANGSMITH_API_KEY", settings.langsmith_api_key)
