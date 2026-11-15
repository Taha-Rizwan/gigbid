"""Loads agent/config.yaml once. Every model, threshold and rule comes from here."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(os.environ.get("GIGBID_CONFIG", ROOT / "agent" / "config.yaml"))
PROMPTS_DIR = ROOT / "agent" / "prompts"

load_dotenv(ROOT / ".env")


@lru_cache(maxsize=1)
def config() -> dict[str, Any]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if mode := os.environ.get("MARKETPLACE_MODE"):
        cfg["marketplace"]["mode"] = mode
    if profile := os.environ.get("MODEL_PROFILE"):
        cfg["models"]["profile"] = profile
    if variant := os.environ.get("RAG_VARIANT"):  # e.g. a low-memory deployment without the reranker
        cfg["rag"]["variant"] = variant
    return cfg


def reload() -> dict[str, Any]:
    config.cache_clear()
    load_prompt.cache_clear()
    return config()


def model_spec(node: str, profile: str | None = None) -> dict[str, Any]:
    """The model a node uses, resolved through its tier in the active profile."""
    cfg = config()["models"]
    tier = cfg["nodes"].get(node, node)  # allows passing a tier name directly ("judge")
    return dict(cfg["profiles"][profile or cfg["profile"]][tier])


@lru_cache(maxsize=64)
def load_prompt(name: str) -> tuple[str, str]:
    """Returns (version, body) of agent/prompts/<name>.md. Front matter holds the version."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    version = "0"
    if text.startswith("---"):
        _, front, text = text.split("---", 2)
        version = str(yaml.safe_load(front).get("version", "0"))
    return version, text.strip()
