"""Two chunkers: the V0 fixed-window baseline and a structure-aware one used by the other variants."""

from __future__ import annotations

import re

from rag.types import Chunk, Doc


def fixed_chunks(doc: Doc, size: int = 600, overlap: int = 80) -> list[Chunk]:
    text = " ".join(doc.text.split())
    step = max(1, size - overlap)
    out = []
    for i, start in enumerate(range(0, max(1, len(text)), step)):
        piece = text[start : start + size]
        if piece.strip():
            out.append(Chunk(f"{doc.evidence_id}#f{i}", doc.evidence_id, doc.persona_id, piece, "fixed"))
        if start + size >= len(text):
            break
    return out


def _split_paragraphs(text: str, size: int) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n|(?=^#{1,3} )", text, flags=re.M) if b and b.strip()]
    out, cur = [], ""
    for b in blocks:
        if len(cur) + len(b) + 1 <= size:
            cur = f"{cur}\n{b}" if cur else b
        else:
            if cur:
                out.append(cur)
            while len(b) > size * 1.5:
                out.append(b[:size])
                b = b[size - 80 :]
            cur = b
    if cur:
        out.append(cur)
    return out


def structured_chunks(doc: Doc, size: int = 600, multivector: bool = True) -> list[Chunk]:
    """Header line with title/project/skills on every chunk. With multivector (V5), a repo is
    indexed as separate summary, README and code vectors that all resolve to one project."""
    header = f"[{doc.type}] {doc.title}"
    if doc.project:
        header += f" | project: {doc.project}"
    if doc.skills:
        header += f" | skills: {', '.join(doc.skills)}"
    meta = {"type": doc.type, "outcome": doc.outcome, "date": doc.date, "project": doc.project}
    out: list[Chunk] = [
        Chunk(f"{doc.evidence_id}#s", doc.evidence_id, doc.persona_id, f"{header}\n{doc.summary(400)}", "summary", meta)
    ]
    if multivector and doc.type == "repo" and doc.parts:
        for kind in ("readme", "code"):
            for i, piece in enumerate(_split_paragraphs(doc.parts.get(kind, ""), size)):
                out.append(Chunk(f"{doc.evidence_id}#{kind}{i}", doc.evidence_id, doc.persona_id, f"{header}\n{piece}", kind, meta))
        return out
    for i, piece in enumerate(_split_paragraphs(doc.text, size)):
        out.append(Chunk(f"{doc.evidence_id}#b{i}", doc.evidence_id, doc.persona_id, f"{header}\n{piece}", "body", meta))
    return out
