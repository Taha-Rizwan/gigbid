"""Runtime configuration for GigSim, read from environment variables (and `.env` if present)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_START = "2024-02-20T09:00:00Z"
DEFAULT_MODEL = "openai/gpt-oss-20b"


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (accepts a trailing `Z`) into an aware UTC datetime."""
    text = value.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_dotenv_if_present() -> None:
    """Load `.env` from the working directory (or a parent) without overriding real env vars."""
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:  # pragma: no cover - python-dotenv is a declared dependency
        return
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path, override=False)


@dataclass
class Config:
    db_path: Path = Path("data/cache/gigsim.sqlite")
    seed_dir: Path = Path("data/processed/gigsim_seed")
    admin_token: str = "gigsim-admin"
    rate_per_min: float = 60.0
    error_rate: float = 0.02
    start: datetime = field(default_factory=lambda: parse_iso(DEFAULT_START))
    clock_speed: float = 0.0
    seed: int = 42
    llm_model: str = DEFAULT_MODEL
    llm_disabled: bool = False
    llm_timeout: float = 20.0
    # repr=False so the key never shows up in logs or tracebacks.
    groq_api_key: str | None = field(default=None, repr=False)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key) and not self.llm_disabled

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, *, load_dotenv: bool = True) -> Config:
        if env is None:
            if load_dotenv:
                load_dotenv_if_present()
            env = os.environ
        return cls(
            db_path=Path(env.get("GIGSIM_DB", "data/cache/gigsim.sqlite")),
            seed_dir=Path(env.get("GIGSIM_SEED_DIR", "data/processed/gigsim_seed")),
            admin_token=env.get("GIGSIM_ADMIN_TOKEN", "gigsim-admin"),
            rate_per_min=float(env.get("GIGSIM_RATE_PER_MIN", "60")),
            error_rate=float(env.get("GIGSIM_ERROR_RATE", "0.02")),
            start=parse_iso(env.get("GIGSIM_START", DEFAULT_START)),
            clock_speed=float(env.get("GIGSIM_CLOCK_SPEED", "0")),
            seed=int(env.get("GIGSIM_SEED", "42")),
            llm_model=env.get("GIGSIM_LLM_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL,
            llm_disabled=_truthy(env.get("GIGSIM_LLM_DISABLED")),
            llm_timeout=float(env.get("GIGSIM_LLM_TIMEOUT", "20")),
            groq_api_key=(env.get("GROQ_API_KEY") or "").strip() or None,
        )
