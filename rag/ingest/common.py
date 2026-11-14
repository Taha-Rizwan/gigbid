"""Shared helpers for the data build scripts."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
PERSONAS_DIR = DATA / "personas"
EVALS_DIR = ROOT / "evals" / "datasets"
SPECS_PATH = ROOT / "scripts" / "persona_specs.yaml"

GEN_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]   # generation; 20b only if 120b hits its daily cap
LABEL_MODELS = ["qwen/qwen3.8-27b"]                          # gold labelling: a different model family
PERSONA_IDS = ["ai_ml", "fullstack", "data_analyst"]


def load_specs() -> dict[str, dict]:
    return yaml.safe_load(SPECS_PATH.read_text(encoding="utf-8"))["personas"]


def stable_int(*parts: Any, mod: int = 2**31 - 1) -> int:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:12], 16) % mod


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w[\w'-]*\b", text))


def generator(model: str, prompt_version: str, seed: int) -> dict:
    return {"model": model, "prompt_version": prompt_version, "seed": seed}


def persona_catalogue(persona_id: str) -> list[dict]:
    """All evidence items of a persona (from index.jsonl): {evidence_id, type, title, summary, ...}."""
    return read_jsonl(PERSONAS_DIR / persona_id / "index.jsonl")
