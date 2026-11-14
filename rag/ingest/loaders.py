"""Loaders for every portfolio source: PDF/Markdown CVs, case studies, repos, reviews, proposals.

Repos can come from local files or through the GitHub MCP server (rag/ingest/github_ingest.py).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from rag.types import Doc

ROOT = Path(__file__).resolve().parents[2]
PERSONAS_DIR = Path(os.environ.get("GIGBID_PERSONAS_DIR", ROOT / "data" / "personas")).resolve()


def _rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".sql", ".ipynb", ".r", ".go", ".yml", ".yaml", ".toml"}


def _front_matter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        _, front, body = text.split("---", 2)
        return yaml.safe_load(front) or {}, body.strip()
    return {}, text


def read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    return "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)


def load_cv(pdir: Path, persona_id: str) -> Doc | None:
    pdf, md = pdir / "cv.pdf", pdir / "cv.md"
    if pdf.exists():
        text, src = read_pdf(pdf), _rel(pdf)
    elif md.exists():
        text, src = md.read_text(encoding="utf-8"), _rel(md)
    else:
        return None
    return Doc(f"{persona_id}:cv", persona_id, "cv", "Curriculum vitae", text, source=src)


def load_case_studies(pdir: Path, persona_id: str) -> list[Doc]:
    out = []
    for f in sorted((pdir / "case_studies").glob("*.md")):
        meta, body = _front_matter(f.read_text(encoding="utf-8"))
        out.append(
            Doc(
                evidence_id=meta.get("evidence_id") or f"{persona_id}:case:{f.stem}",
                persona_id=persona_id,
                type="case",
                title=meta.get("title", f.stem),
                text=body,
                project=meta.get("project"),
                skills=list(meta.get("skills") or []),
                date=str(meta.get("date")) if meta.get("date") else None,
                outcome=str(meta.get("outcome")) if meta.get("outcome") else None,
                client_industry=meta.get("client_industry"),
                source=_rel(f),
                synthetic=bool(meta.get("synthetic", True)),
            )
        )
    return out


def repo_doc(persona_id: str, name: str, files: dict[str, str], source: str) -> Doc:
    readme = next((v for k, v in files.items() if k.lower().endswith("readme.md")), "")
    code = {k: v for k, v in files.items() if Path(k).suffix.lower() in CODE_EXT}
    code_text = "\n\n".join(f"# file: {k}\n{v[:4000]}" for k, v in sorted(code.items()))
    return Doc(
        evidence_id=f"{persona_id}:repo:{name}",
        persona_id=persona_id,
        type="repo",
        title=f"Repository {name}",
        text=f"{readme}\n\n{code_text}".strip(),
        project=name,
        source=source,
        parts={"readme": readme, "code": code_text},
    )


def load_repos_local(pdir: Path, persona_id: str) -> list[Doc]:
    out = []
    for repo in sorted(p for p in (pdir / "repos").glob("*") if p.is_dir()):
        files = {
            str(f.relative_to(repo)).replace("\\", "/"): f.read_text(encoding="utf-8", errors="ignore")
            for f in repo.rglob("*")
            if f.is_file() and (f.suffix.lower() in CODE_EXT or f.name.lower() == "readme.md")
        }
        out.append(repo_doc(persona_id, repo.name, files, _rel(repo)))
    return out


def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_reviews(pdir: Path, persona_id: str) -> list[Doc]:
    return [
        Doc(
            evidence_id=r["evidence_id"],
            persona_id=persona_id,
            type="review",
            title=f"Client review: {r.get('project') or r.get('client_name', '')}",
            text=f"{r['text']} (rating {r.get('rating')}/5, {r.get('client_name', 'client')})",
            project=r.get("project"),
            date=r.get("date"),
            source=f"data/personas/{persona_id}/reviews.jsonl",
        )
        for r in _jsonl(pdir / "reviews.jsonl")
    ]


def load_proposals(pdir: Path, persona_id: str) -> list[Doc]:
    out = []
    for p in _jsonl(pdir / "proposals.jsonl"):
        answers = "\n".join(p.get("screening_answers") or [])
        out.append(
            Doc(
                evidence_id=p["evidence_id"],
                persona_id=persona_id,
                type="proposal",
                title=f"Past proposal: {p.get('job_title', '')}",
                text=f"{p['cover_letter']}\n{answers}".strip(),
                date=p.get("date"),
                outcome=p.get("outcome"),
                source=f"data/personas/{persona_id}/proposals.jsonl",
            )
        )
    return out


def load_persona(persona_id: str, repo_loader=None) -> list[Doc]:
    pdir = PERSONAS_DIR / persona_id
    docs: list[Doc] = []
    if cv := load_cv(pdir, persona_id):
        docs.append(cv)
    docs += load_case_studies(pdir, persona_id)
    docs += (repo_loader or load_repos_local)(pdir, persona_id)
    docs += load_reviews(pdir, persona_id)
    docs += load_proposals(pdir, persona_id)
    return docs


def load_upload(persona_id: str, filename: str, data: bytes, idx: int) -> Doc:
    """User-added work from the UI (incremental re-indexing)."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        import io

        from pypdf import PdfReader

        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    else:
        text = data.decode("utf-8", errors="ignore")
    meta, body = _front_matter(text)
    slug = Path(filename).stem.lower().replace(" ", "-")[:40]
    return Doc(
        evidence_id=meta.get("evidence_id") or f"{persona_id}:upload:{slug}-{idx}",
        persona_id=persona_id,
        type="upload",
        title=meta.get("title") or Path(filename).stem,
        text=body,
        project=meta.get("project"),
        skills=list(meta.get("skills") or []),
        source=f"upload:{filename}",
        synthetic=False,
    )


def list_personas() -> list[str]:
    return sorted(p.name for p in PERSONAS_DIR.glob("*") if (p / "profile.json").exists())
