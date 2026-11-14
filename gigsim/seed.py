"""Load seed data from `GIGSIM_SEED_DIR` (JSON Lines) or the built-in fixtures, and write it to SQLite.

`load_seed(seed_dir)` is the entry point used by the service and by data pipelines that want to
validate their output. A seed directory is used when it contains both `jobs.jsonl` and
`clients.jsonl`; otherwise everything comes from `gigsim/fixtures/`. `accounts.jsonl`,
`market_stats.json` and `competitors.json` each fall back to the fixture copy when missing from the
seed directory.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gigsim.db import dumps

log = logging.getLogger("gigsim.seed")

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

HIDDEN_DEFAULTS: dict[str, Any] = {
    "must_have_skills": [],
    "budget_ceiling_factor": 1.0,
    "dislikes_generic": False,
    "max_words": 250,
    "prefers_questions": False,
    "responsiveness": 0.6,
    "is_scammer": False,
}


class SeedError(ValueError):
    """Raised when seed files are malformed or inconsistent."""


@dataclass
class SeedData:
    jobs: list[dict[str, Any]]
    clients: list[dict[str, Any]]
    accounts: list[dict[str, Any]]
    market_stats: dict[str, Any]
    competitors: dict[str, Any]
    sources: dict[str, str] = field(default_factory=dict)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SeedError(f"{path.name}:{lineno}: invalid JSON ({exc.msg})") from exc
            if not isinstance(obj, dict):
                raise SeedError(f"{path.name}:{lineno}: expected a JSON object")
            rows.append(obj)
    return rows


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


def normalise_job(raw: dict[str, Any]) -> dict[str, Any]:
    for key in ("job_id", "title", "client_id"):
        if not raw.get(key):
            raise SeedError(f"job is missing required field {key!r}: {str(raw)[:120]}")
    is_hourly = bool(raw.get("is_hourly", False))
    return {
        "job_id": str(raw["job_id"]),
        "title": str(raw["title"]).strip(),
        "description": str(raw.get("description") or ""),
        "category": raw.get("category") or "Other",
        "skills": _str_list(raw.get("skills")),
        "is_hourly": is_hourly,
        "hourly_low": _num(raw.get("hourly_low")),
        "hourly_high": _num(raw.get("hourly_high")),
        "budget": _num(raw.get("budget")),
        "country": raw.get("country"),
        "client_id": str(raw["client_id"]),
        "release_minute": int(raw.get("release_minute") or 0),
        "proposals_count": int(raw.get("proposals_count") or 0),
        "screening_questions": _str_list(raw.get("screening_questions")),
        "experience_level": raw.get("experience_level"),
        "is_scam": bool(raw.get("is_scam", False)),
        "has_injection": bool(raw.get("has_injection", False)),
        "duplicate_of": raw.get("duplicate_of") or None,
        "source": raw.get("source") or "unknown",
    }


def normalise_client(raw: dict[str, Any]) -> dict[str, Any]:
    for key in ("client_id", "name"):
        if not raw.get(key):
            raise SeedError(f"client is missing required field {key!r}: {str(raw)[:120]}")
    hidden = {**HIDDEN_DEFAULTS, **(raw.get("hidden") or {})}
    hidden["must_have_skills"] = _str_list(hidden.get("must_have_skills"))
    hidden["budget_ceiling_factor"] = float(hidden["budget_ceiling_factor"] or 1.0)
    hidden["max_words"] = int(hidden["max_words"] or 250)
    hidden["responsiveness"] = min(1.0, max(0.0, float(hidden["responsiveness"])))
    for key in ("dislikes_generic", "prefers_questions", "is_scammer"):
        hidden[key] = bool(hidden[key])
    reviews = []
    for r in raw.get("reviews") or []:
        if isinstance(r, dict):
            reviews.append({"rating": _num(r.get("rating")), "text": str(r.get("text") or "")})
    return {
        "client_id": str(raw["client_id"]),
        "name": str(raw["name"]),
        "country": raw.get("country"),
        "member_since": raw.get("member_since"),
        "total_spent": _num(raw.get("total_spent")) or 0.0,
        "jobs_posted": int(raw.get("jobs_posted") or 0),
        "hires": int(raw.get("hires") or 0),
        "avg_rating": _num(raw.get("avg_rating")),
        "payment_verified": bool(raw.get("payment_verified", False)),
        "reviews": reviews,
        "hidden": hidden,
    }


def normalise_account(raw: dict[str, Any]) -> dict[str, Any]:
    for key in ("account_id", "name", "token"):
        if not raw.get(key):
            raise SeedError(f"account is missing required field {key!r}")
    return {
        "account_id": str(raw["account_id"]),
        "name": str(raw["name"]),
        "title": raw.get("title") or "",
        "hourly_rate": _num(raw.get("hourly_rate")),
        "skills": _str_list(raw.get("skills")),
        "success_score": min(1.0, max(0.0, float(raw.get("success_score", 0.8)))),
        "token": str(raw["token"]),
        "connects_balance": int(raw.get("connects_balance") or 0),
        "weekly_allowance": int(raw.get("weekly_allowance") or 0),
    }


def _pick(seed_dir: Path | None, name: str) -> Path:
    if seed_dir is not None and (seed_dir / name).is_file():
        return seed_dir / name
    return FIXTURES_DIR / name


def load_seed(seed_dir: str | os.PathLike[str] | None = None) -> SeedData:
    """Load and validate seed data.

    `seed_dir` is used when it contains `jobs.jsonl` and `clients.jsonl`; otherwise the built-in
    fixtures are used. Missing `accounts.jsonl` / `market_stats.json` / `competitors.json` fall
    back to the fixture copies individually.
    """
    base: Path | None = Path(seed_dir) if seed_dir is not None else None
    if base is not None and not ((base / "jobs.jsonl").is_file() and (base / "clients.jsonl").is_file()):
        base = None
    sources: dict[str, str] = {}

    def path_for(name: str) -> Path:
        p = FIXTURES_DIR / name if base is None else _pick(base, name)
        sources[name] = str(p)
        return p

    jobs = [normalise_job(r) for r in read_jsonl(path_for("jobs.jsonl"))]
    clients = [normalise_client(r) for r in read_jsonl(path_for("clients.jsonl"))]
    accounts = [normalise_account(r) for r in read_jsonl(path_for("accounts.jsonl"))]
    with path_for("market_stats.json").open(encoding="utf-8") as fh:
        market_stats = json.load(fh)
    with path_for("competitors.json").open(encoding="utf-8") as fh:
        competitors = json.load(fh)

    data = SeedData(jobs, clients, accounts, market_stats, competitors, sources)
    validate(data)
    return data


def validate(data: SeedData) -> None:
    def unique(rows: list[dict[str, Any]], key: str, label: str) -> set[str]:
        seen: set[str] = set()
        for r in rows:
            if r[key] in seen:
                raise SeedError(f"duplicate {label} id {r[key]!r}")
            seen.add(r[key])
        return seen

    job_ids = unique(data.jobs, "job_id", "job")
    client_ids = unique(data.clients, "client_id", "client")
    unique(data.accounts, "account_id", "account")
    unique(data.accounts, "token", "account token")
    for job in data.jobs:
        if job["client_id"] not in client_ids:
            raise SeedError(f"job {job['job_id']} references unknown client {job['client_id']!r}")
        if job["duplicate_of"] and job["duplicate_of"] not in job_ids:
            raise SeedError(f"job {job['job_id']} duplicate_of unknown job {job['duplicate_of']!r}")
    if not data.accounts:
        raise SeedError("no accounts in seed data")
    q = data.competitors.get("quality_quantiles")
    if not isinstance(q, list) or len(q) < 2:
        raise SeedError("competitors.json needs quality_quantiles (21 floats in 0..1)")


def write_seed(conn: sqlite3.Connection, data: SeedData) -> None:
    """Insert seed rows. Assumes empty tables (call after `drop_resettable`)."""
    for a in data.accounts:
        conn.execute(
            "INSERT INTO accounts(account_id, name, title, hourly_rate, skills, success_score, token,"
            " connects_balance, weekly_allowance) VALUES (?,?,?,?,?,?,?,?,?)",
            (a["account_id"], a["name"], a["title"], a["hourly_rate"], dumps(a["skills"]),
             a["success_score"], a["token"], a["connects_balance"], a["weekly_allowance"]),
        )
    for c in data.clients:
        conn.execute(
            "INSERT INTO clients(client_id, name, country, member_since, total_spent, jobs_posted, hires,"
            " avg_rating, payment_verified, reviews, hidden) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (c["client_id"], c["name"], c["country"], c["member_since"], c["total_spent"],
             c["jobs_posted"], c["hires"], c["avg_rating"], int(c["payment_verified"]),
             dumps(c["reviews"]), dumps(c["hidden"])),
        )
    for j in data.jobs:
        conn.execute(
            "INSERT INTO jobs(job_id, title, description, category, skills, is_hourly, hourly_low,"
            " hourly_high, budget, country, client_id, release_minute, base_proposals,"
            " screening_questions, experience_level, is_scam, has_injection, duplicate_of, source)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (j["job_id"], j["title"], j["description"], j["category"], dumps(j["skills"]),
             int(j["is_hourly"]), j["hourly_low"], j["hourly_high"], j["budget"], j["country"],
             j["client_id"], j["release_minute"], j["proposals_count"],
             dumps(j["screening_questions"]), j["experience_level"], int(j["is_scam"]),
             int(j["has_injection"]), j["duplicate_of"], j["source"]),
        )
    conn.execute("INSERT INTO meta(key, value) VALUES ('market_stats', ?)", (dumps(data.market_stats),))
    conn.execute("INSERT INTO meta(key, value) VALUES ('competitors', ?)", (dumps(data.competitors),))
    conn.execute("INSERT INTO meta(key, value) VALUES ('seed_sources', ?)", (dumps(data.sources),))
    log.info("seeded %d jobs, %d clients, %d accounts", len(data.jobs), len(data.clients), len(data.accounts))
