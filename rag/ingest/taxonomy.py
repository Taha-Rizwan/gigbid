"""Keyword taxonomy + skill lexicon loaded from data/taxonomy.yaml."""
from __future__ import annotations

import re
from functools import lru_cache

import yaml

from rag.ingest.common import DATA

TAXONOMY_PATH = DATA / "taxonomy.yaml"


def _rx(alts: list[str]) -> re.Pattern:
    return re.compile(r"(?<![\w])(?:" + "|".join(f"(?:{a})" for a in alts) + r")(?![\w])", re.I)


@lru_cache(maxsize=1)
def load() -> dict:
    t = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    t["_cat_rx"] = {c: _rx(v["keywords"]) for c, v in t["categories"].items() if v["keywords"]}
    t["_skill_rx"] = {s: _rx(alts) for s, alts in t["skills"].items()}
    return t


def categorize(title: str, description: str = "") -> tuple[str, int]:
    t = load()
    title = title or ""
    description = (description or "")[:4000]
    best, best_score = "other", 0
    for cat, rx in t["_cat_rx"].items():
        th = {m.group(0).lower() for m in rx.finditer(title)}
        dh = {m.group(0).lower() for m in rx.finditer(description)} if description else set()
        score = t["title_weight"] * len(th) + min(t["description_cap"], len(dh))
        if score > best_score:
            best, best_score = cat, score
    if best_score < t["min_score"]:
        return "other", best_score
    return best, best_score


def extract_skills(text: str, limit: int = 10) -> list[str]:
    t = load()
    text = (text or "")[:5000]
    found = []
    for skill, rx in t["_skill_rx"].items():
        m = rx.search(text)
        if m:
            found.append((m.start(), skill))
    found.sort()
    return [s for _, s in found][:limit]


def persona_categories(persona_id: str) -> dict[str, list[str]]:
    return load()["personas"][persona_id]


def category_names() -> list[str]:
    return list(load()["categories"])
