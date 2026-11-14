from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Doc:
    """One portfolio evidence item (case study, repo, review, CV, past proposal, upload)."""

    evidence_id: str
    persona_id: str
    type: str  # cv | case | repo | review | proposal | upload
    title: str
    text: str
    project: str | None = None
    skills: list[str] = field(default_factory=list)
    date: str | None = None
    outcome: str | None = None
    client_industry: str | None = None
    source: str = ""
    synthetic: bool = True
    parts: dict[str, str] = field(default_factory=dict)  # repo: readme / code / summary

    def summary(self, n: int = 240) -> str:
        return " ".join(self.text.split())[:n]


@dataclass
class Chunk:
    chunk_id: str
    evidence_id: str
    persona_id: str
    text: str
    kind: str = "body"  # body | readme | code | summary | fixed
    meta: dict[str, Any] = field(default_factory=dict)
    context: str = ""  # V6 contextual line

    @property
    def embed_text(self) -> str:
        return f"{self.context}\n{self.text}" if self.context else self.text
