"""Core simulator logic, independent of HTTP. `app.py` maps routes onto these methods.

Write paths that may call the LLM (submit, post message) run in three phases so the slow call never
holds the database lock: (1) validate in a transaction, (2) compute outside it, (3) re-validate and
commit in a second transaction. Idempotency records are checked in both (1) and (3), so a repeated
key can never spend Connects twice.
"""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any

from gigsim import client_model, clock
from gigsim.config import Config, parse_iso
from gigsim.db import Store, drop_resettable, dumps, loads, meta_get, meta_set, next_id
from gigsim.llm import LLM
from gigsim.policy import PolicyBook, PolicyVersion, check_message, check_proposal, connects_cost
from gigsim.seed import load_seed, write_seed

# Hidden or internal job columns that /v1 never returns.
HIDDEN_JOB_FIELDS = {"is_scam", "has_injection", "duplicate_of", "source", "release_minute", "released",
                     "base_proposals", "sim_proposals"}
PROPOSAL_STATUSES = ("submitted", "viewed", "replied", "interview", "hired", "declined")
REPLY_ALLOWED_OUTCOMES = ("replied", "interview", "hired")


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: str, *, headers: dict[str, str] | None = None, **extra: Any):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail
        self.headers = headers or {}
        self.extra = extra

    def body(self) -> dict[str, Any]:
        return {"error": self.code, "detail": self.detail, **self.extra}


@dataclass
class Result:
    """A JSON response plus whether it was replayed from the idempotency store."""

    body: dict[str, Any]
    status: int = 200
    replayed: bool = False


class RateLimiter:
    """Token bucket per account: capacity = rate per minute, refilled continuously."""

    def __init__(self, rate_per_min: float):
        self.rate = float(rate_per_min)
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def check(self, key: str) -> None:
        if self.rate <= 0:
            return
        per_sec = self.rate / 60.0
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (self.rate, now))
            tokens = min(self.rate, tokens + (now - last) * per_sec)
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return
            self._buckets[key] = (tokens, now)
        retry_after = max(1, math.ceil((1.0 - tokens) / per_sec))
        raise ApiError(
            429, "rate_limited", f"rate limit of {self.rate:g} requests/minute exceeded",
            headers={"Retry-After": str(retry_after)}, retry_after=retry_after,
        )


def _job_dict(row: sqlite3.Row) -> dict[str, Any]:
    job = dict(row)
    job["skills"] = loads(job["skills"], [])
    job["screening_questions"] = loads(job["screening_questions"], [])
    job["is_hourly"] = bool(job["is_hourly"])
    job["is_scam"] = bool(job["is_scam"])
    job["has_injection"] = bool(job["has_injection"])
    job["proposals_count"] = int(job["base_proposals"]) + int(job["sim_proposals"])
    return job


def _client_dict(row: sqlite3.Row) -> dict[str, Any]:
    client = dict(row)
    client["reviews"] = loads(client["reviews"], [])
    client["hidden"] = loads(client["hidden"], {})
    client["payment_verified"] = bool(client["payment_verified"])
    return client


def _account_dict(row: sqlite3.Row) -> dict[str, Any]:
    acct = dict(row)
    acct["skills"] = loads(acct["skills"], [])
    return acct


_QUERY_STOP = client_model.STOPWORDS | {"job", "jobs"}


class Simulator:
    def __init__(self, config: Config):
        self.cfg = config
        self.store = Store(config.db_path)
        self.policies = PolicyBook.load()
        self.llm = LLM(
            self.store, config.groq_api_key, config.llm_model,
            disabled=config.llm_disabled, timeout=config.llm_timeout,
        )
        self.limiter = RateLimiter(config.rate_per_min)
        self.seed = config.seed
        self._request_counter = 0
        self._counter_lock = threading.Lock()
        self._ready = False
        self._init_lock = threading.Lock()

    # --- lifecycle --------------------------------------------------------------------------

    def ensure_ready(self) -> None:
        if self._ready:
            return
        with self._init_lock:
            if self._ready:
                return
            self.store.init()
            with self.store.tx() as conn:
                if meta_get(conn, "seeded") is None:
                    drop_resettable(conn)
                    self._seed(conn, self.cfg.seed)
                self.seed = int(meta_get(conn, "seed", str(self.cfg.seed)) or self.cfg.seed)
            self._ready = True

    def _seed(self, conn: sqlite3.Connection, seed: int) -> None:
        data = load_seed(self.cfg.seed_dir)
        write_seed(conn, data)
        meta_set(conn, "seed", seed)
        meta_set(conn, "clock_minute", 0)
        meta_set(conn, "connects_week", 0)
        meta_set(conn, "policy_version", self.policies.default)
        clock.process_due(conn, 0)  # release jobs with release_minute <= 0
        meta_set(conn, "seeded", 1)

    def reset(self, seed: int | None = None) -> dict[str, Any]:
        self.ensure_ready()
        seed = self.cfg.seed if seed is None else int(seed)
        with self.store.tx() as conn:
            drop_resettable(conn)
            self._seed(conn, seed)
            counts = {
                "jobs": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
                "released_jobs": conn.execute("SELECT COUNT(*) FROM jobs WHERE released = 1").fetchone()[0],
                "clients": conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0],
                "accounts": conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
            }
            sources = loads(meta_get(conn, "seed_sources"), {})
        self.seed = seed
        self.limiter.reset()
        with self._counter_lock:
            self._request_counter = 0
        return {"ok": True, "seed": seed, "now": clock.iso_at(self.cfg.start, 0), "counts": counts,
                "seed_sources": sources}

    # --- guards -----------------------------------------------------------------------------

    def authenticate(self, authorization: str | None) -> dict[str, Any]:
        self.ensure_ready()
        if not authorization or not authorization.lower().startswith("bearer "):
            raise ApiError(401, "unauthorized", "missing bearer token")
        token = authorization[7:].strip()
        with self.store.tx() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE token = ?", (token,)).fetchone()
        if row is None:
            raise ApiError(401, "unauthorized", "unknown account token")
        return _account_dict(row)

    def chaos(self) -> None:
        with self._counter_lock:
            self._request_counter += 1
            counter = self._request_counter
        if self.cfg.error_rate <= 0:
            return
        digest = hashlib.sha256(f"chaos:{self.seed}:{counter}".encode()).digest()
        if int.from_bytes(digest[:8], "big") / 2**64 < self.cfg.error_rate:
            raise ApiError(503, "upstream_unavailable", "simulated upstream failure, retry later",
                           headers={"Retry-After": "1"})

    def check_admin(self, token: str | None) -> None:
        self.ensure_ready()
        if token != self.cfg.admin_token:
            raise ApiError(401, "unauthorized", "missing or invalid X-Admin-Token")

    # --- shared helpers ---------------------------------------------------------------------

    def _policy(self, conn: sqlite3.Connection) -> PolicyVersion:
        return self.policies.get(meta_get(conn, "policy_version", self.policies.default) or self.policies.default)

    def _iso(self, minute: int) -> str:
        return clock.iso_at(self.cfg.start, minute)

    def _public_job(self, job: dict[str, Any], pv: PolicyVersion, *, summary: bool) -> dict[str, Any]:
        out = {k: v for k, v in job.items() if k not in HIDDEN_JOB_FIELDS}
        out["posted_at"] = self._iso(job["release_minute"])
        out["connects_cost"] = connects_cost(job, pv, job["proposals_count"])
        if summary:
            desc = out.pop("description", "") or ""
            out["snippet"] = desc[:280]
        return out

    def _load_job(self, conn: sqlite3.Connection, job_id: str, *, released_only: bool) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None or (released_only and not row["released"]):
            raise ApiError(404, "job_not_found", f"job {job_id} not found")
        return _job_dict(row)

    def _load_client(self, conn: sqlite3.Connection, client_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM clients WHERE client_id = ?", (client_id,)).fetchone()
        if row is None:
            raise ApiError(404, "client_not_found", f"client {client_id} not found")
        return _client_dict(row)

    def _load_account(self, conn: sqlite3.Connection, account_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
        if row is None:
            raise ApiError(404, "account_not_found", f"account {account_id} not found")
        return _account_dict(row)

    @staticmethod
    def _idem_get(conn: sqlite3.Connection, account_id: str, key: str, path: str) -> Result | None:
        row = conn.execute(
            "SELECT * FROM idempotency WHERE account_id = ? AND idem_key = ?", (account_id, key)
        ).fetchone()
        if row is None:
            return None
        if row["path"] != path:
            raise ApiError(409, "idempotency_key_reused",
                           f"Idempotency-Key was already used for {row['path']}")
        return Result(loads(row["response"], {}), row["status_code"], replayed=True)

    @staticmethod
    def _idem_put(conn: sqlite3.Connection, account_id: str, key: str, path: str, result: Result) -> None:
        conn.execute(
            "INSERT INTO idempotency(account_id, idem_key, path, status_code, response) VALUES (?,?,?,?,?)",
            (account_id, key, path, result.status, dumps(result.body)),
        )

    @staticmethod
    def _require_key(key: str | None) -> str:
        if not key or not key.strip():
            raise ApiError(400, "missing_idempotency_key", "this endpoint requires an Idempotency-Key header")
        if len(key) > 200:
            raise ApiError(400, "invalid_idempotency_key", "Idempotency-Key must be at most 200 characters")
        return key.strip()

    # --- read endpoints ---------------------------------------------------------------------

    def search_jobs(self, *, q: str | None, category: str | None, skills: str | None,
                    posted_after: str | None, limit: int, offset: int) -> dict[str, Any]:
        after_minute: float | None = None
        if posted_after:
            try:
                after_minute = clock.minute_of(self.cfg.start, parse_iso(posted_after))
            except ValueError as exc:
                raise ApiError(400, "invalid_parameter", "posted_after must be an ISO-8601 timestamp") from exc
        terms = [t for t in re.findall(r"[a-z0-9][a-z0-9+#.-]*", (q or "").lower()) if t not in _QUERY_STOP]
        wanted_skills = {s.strip().lower() for s in (skills or "").split(",") if s.strip()}
        with self.store.tx() as conn:
            pv = self._policy(conn)
            rows = conn.execute("SELECT * FROM jobs WHERE released = 1").fetchall()
        scored: list[tuple[int, int, str, dict[str, Any]]] = []
        for row in rows:
            job = _job_dict(row)
            if category and (job["category"] or "").lower() != category.strip().lower():
                continue
            if wanted_skills and not wanted_skills & {s.lower() for s in job["skills"]}:
                continue
            if after_minute is not None and job["release_minute"] <= after_minute:
                continue
            hits = 0
            if terms:
                hay = f"{job['title']}\n{job['description']}".lower()
                hits = sum(1 for t in terms if client_model.mentions(t, hay))
                if hits == 0:
                    continue
            scored.append((hits, job["release_minute"], job["job_id"], job))
        scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
        page = scored[offset: offset + limit]
        return {"jobs": [self._public_job(j, pv, summary=True) for *_, j in page], "total": len(scored)}

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.store.tx() as conn:
            pv = self._policy(conn)
            job = self._load_job(conn, job_id, released_only=True)
        return self._public_job(job, pv, summary=False)

    def get_client(self, client_id: str) -> dict[str, Any]:
        with self.store.tx() as conn:
            c = self._load_client(conn, client_id)
        jobs_posted = c["jobs_posted"] or 0
        return {
            "client_id": c["client_id"],
            "name": c["name"],
            "country": c["country"],
            "member_since": c["member_since"],
            "total_spent": c["total_spent"],
            "jobs_posted": jobs_posted,
            "hires": c["hires"],
            "hire_rate": round(c["hires"] / jobs_posted, 3) if jobs_posted else 0.0,
            "avg_rating": c["avg_rating"],
            "payment_verified": c["payment_verified"],
            "reviews": c["reviews"],
        }

    def get_connects(self, account: dict[str, Any]) -> dict[str, Any]:
        with self.store.tx() as conn:
            acct = self._load_account(conn, account["account_id"])
            now = clock.now_minute(conn)
        return {"balance": acct["connects_balance"], "weekly_allowance": acct["weekly_allowance"],
                "resets_at": clock.resets_at(self.cfg.start, now)}

    def market_stats(self, category: str | None) -> dict[str, Any]:
        with self.store.tx() as conn:
            stats = loads(meta_get(conn, "market_stats"), {})
        key = category or "_all"
        if key not in stats:
            lowered = {k.lower(): k for k in stats}
            if key.lower() in lowered:
                key = lowered[key.lower()]
            else:
                raise ApiError(404, "unknown_category",
                               f"no market stats for {category!r}; available: {', '.join(sorted(stats))}")
        return {"category": key, **stats[key]}

    def get_policy(self) -> dict[str, Any]:
        with self.store.tx() as conn:
            return self._policy(conn).public()

    def list_proposals(self, account: dict[str, Any], status: str | None) -> dict[str, Any]:
        if status and status not in PROPOSAL_STATUSES:
            raise ApiError(400, "invalid_parameter", f"status must be one of {', '.join(PROPOSAL_STATUSES)}")
        sql = ("SELECT p.*, j.title AS job_title FROM proposals p JOIN jobs j ON j.job_id = p.job_id"
               " WHERE p.account_id = ?")
        params: list[Any] = [account["account_id"]]
        if status:
            sql += " AND p.status = ?"
            params.append(status)
        sql += " ORDER BY p.submitted_minute DESC, p.proposal_id DESC"
        with self.store.tx() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {"proposals": [
            {
                "proposal_id": r["proposal_id"], "job_id": r["job_id"], "job_title": r["job_title"],
                "status": r["status"], "bid_amount": r["bid_amount"], "rate_type": r["rate_type"],
                "connects_spent": r["connects_spent"],
                "submitted_at": self._iso(r["submitted_minute"]), "updated_at": self._iso(r["updated_minute"]),
                "thread_id": r["thread_id"],
            }
            for r in rows
        ]}

    def list_threads(self, account: dict[str, Any]) -> dict[str, Any]:
        with self.store.tx() as conn:
            rows = conn.execute(
                "SELECT t.*, c.name AS client_name FROM threads t JOIN clients c ON c.client_id = t.client_id"
                " WHERE t.account_id = ? ORDER BY t.last_message_minute DESC, t.thread_id DESC",
                (account["account_id"],),
            ).fetchall()
        return {"threads": [
            {"thread_id": r["thread_id"], "proposal_id": r["proposal_id"], "job_id": r["job_id"],
             "client_id": r["client_id"], "client_name": r["client_name"],
             "last_message_at": self._iso(r["last_message_minute"]), "unread": r["unread"]}
            for r in rows
        ]}

    def _owned_thread(self, conn: sqlite3.Connection, account_id: str, thread_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM threads WHERE thread_id = ? AND account_id = ?",
                           (thread_id, account_id)).fetchone()
        if row is None:
            raise ApiError(404, "thread_not_found", f"thread {thread_id} not found")
        return row

    def get_messages(self, account: dict[str, Any], thread_id: str) -> dict[str, Any]:
        with self.store.tx() as conn:
            self._owned_thread(conn, account["account_id"], thread_id)
            rows = conn.execute("SELECT * FROM messages WHERE thread_id = ? ORDER BY seq", (thread_id,)).fetchall()
            conn.execute("UPDATE threads SET unread = 0 WHERE thread_id = ?", (thread_id,))
        return {"messages": [
            {"message_id": r["message_id"], "sender": r["sender"], "text": r["text"],
             "sent_at": self._iso(r["sent_minute"])}
            for r in rows
        ]}

    def list_events(self, account: dict[str, Any], after: int, limit: int) -> dict[str, Any]:
        with self.store.tx() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE event_id > ? AND (account_id IS NULL OR account_id = ?)"
                " ORDER BY event_id LIMIT ?",
                (after, account["account_id"], limit),
            ).fetchall()
        events = [clock.event_public(r, self.cfg.start) for r in rows]
        return {"events": events, "next_cursor": events[-1]["event_id"] if events else after}

    # --- drafts and submission --------------------------------------------------------------

    def create_draft(self, account: dict[str, Any], key: str | None, body: dict[str, Any]) -> Result:
        key = self._require_key(key)
        path = "/v1/proposals/drafts"
        with self.store.tx() as conn:
            replay = self._idem_get(conn, account["account_id"], key, path)
            if replay:
                return replay
            job = self._load_job(conn, body["job_id"], released_only=True)
            expected = "hourly" if job["is_hourly"] else "fixed"
            if body["rate_type"] != expected:
                raise ApiError(422, "rate_type_mismatch",
                               f"job {job['job_id']} is {expected}; rate_type must be {expected!r}")
            pv = self._policy(conn)
            cost = connects_cost(job, pv, job["proposals_count"])
            now = clock.now_minute(conn)
            draft_id = next_id(conn, "dr")
            conn.execute(
                "INSERT INTO drafts(draft_id, account_id, job_id, cover_letter, screening_answers, bid_amount,"
                " rate_type, connects_cost, created_minute, status) VALUES (?,?,?,?,?,?,?,?,?, 'draft')",
                (draft_id, account["account_id"], job["job_id"], body["cover_letter"],
                 dumps(body["screening_answers"]), float(body["bid_amount"]), body["rate_type"], cost, now),
            )
            result = Result({"draft_id": draft_id, "job_id": job["job_id"], "status": "draft",
                             "connects_cost": cost, "created_at": self._iso(now)})
            self._idem_put(conn, account["account_id"], key, path, result)
        return result

    def _submit_context(self, conn: sqlite3.Connection, account_id: str, draft_id: str) -> dict[str, Any]:
        draft = conn.execute("SELECT * FROM drafts WHERE draft_id = ? AND account_id = ?",
                             (draft_id, account_id)).fetchone()
        if draft is None:
            raise ApiError(404, "draft_not_found", f"draft {draft_id} not found")
        job = self._load_job(conn, draft["job_id"], released_only=True)
        client = self._load_client(conn, job["client_id"])
        acct = self._load_account(conn, account_id)
        pv = self._policy(conn)
        answers = loads(draft["screening_answers"], [])
        return {
            "draft": dict(draft), "answers": answers, "job": job, "client": client, "account": acct,
            "pv": pv, "cost": connects_cost(job, pv, job["proposals_count"]),
            "violations": check_proposal(pv, draft["cover_letter"], answers),
        }

    def _submit_blockers(self, conn: sqlite3.Connection, ctx: dict[str, Any]) -> None:
        if ctx["violations"]:
            raise ApiError(422, "policy_violation", "proposal violates platform policy "
                           f"{ctx['pv'].name}", violations=ctx["violations"])
        if ctx["draft"]["status"] != "draft":
            raise ApiError(409, "already_submitted", f"draft {ctx['draft']['draft_id']} was already submitted")
        existing = conn.execute("SELECT proposal_id FROM proposals WHERE account_id = ? AND job_id = ?",
                                (ctx["account"]["account_id"], ctx["job"]["job_id"])).fetchone()
        if existing:
            raise ApiError(409, "already_applied",
                           f"this account already applied to {ctx['job']['job_id']} ({existing['proposal_id']})")
        balance = ctx["account"]["connects_balance"]
        if balance < ctx["cost"]:
            raise ApiError(402, "insufficient_connects",
                           f"submitting costs {ctx['cost']} Connects but the balance is {balance}",
                           connects_cost=ctx["cost"], balance=balance)

    def submit_draft(self, account: dict[str, Any], draft_id: str, key: str | None, dry_run: bool) -> Result:
        key = self._require_key(key)
        account_id = account["account_id"]
        path = f"/v1/proposals/drafts/{draft_id}/submit"

        # Phase 1: validate.
        with self.store.tx() as conn:
            if not dry_run:
                replay = self._idem_get(conn, account_id, key, path)
                if replay:
                    return replay
            ctx = self._submit_context(conn, account_id, draft_id)
            if dry_run:
                d = ctx["draft"]
                balance = ctx["account"]["connects_balance"]
                return Result({
                    "would_send": {
                        "draft_id": d["draft_id"], "job_id": d["job_id"], "account_id": account_id,
                        "cover_letter": d["cover_letter"], "screening_answers": ctx["answers"],
                        "bid_amount": d["bid_amount"], "rate_type": d["rate_type"],
                    },
                    "connects_cost": ctx["cost"],
                    "balance_after": balance - ctx["cost"],
                    "policy_check": {"ok": not ctx["violations"], "violations": ctx["violations"]},
                })
            self._submit_blockers(conn, ctx)
            quantiles = loads(meta_get(conn, "competitors"), {}).get("quality_quantiles") or [0.5, 0.5]
            seed = int(meta_get(conn, "seed", str(self.seed)) or self.seed)

        # Phase 2: decide the outcome (may call the LLM; no lock held).
        d = ctx["draft"]
        score = client_model.score_proposal(
            job=ctx["job"], client=ctx["client"], account=ctx["account"], cover_letter=d["cover_letter"],
            screening_answers=ctx["answers"], bid_amount=d["bid_amount"], rate_type=d["rate_type"],
            quantiles=quantiles, seed=seed, llm=self.llm,
        )
        plan = client_model.plan_events(
            score=score, job=ctx["job"], client=ctx["client"], account=ctx["account"],
            cover_letter=d["cover_letter"], llm=self.llm,
        )

        # Phase 3: re-validate and commit.
        with self.store.tx() as conn:
            replay = self._idem_get(conn, account_id, key, path)
            if replay:
                return replay
            ctx = self._submit_context(conn, account_id, draft_id)
            self._submit_blockers(conn, ctx)
            now = clock.now_minute(conn)
            proposal_id = next_id(conn, "pr")
            cost = ctx["cost"]
            conn.execute("UPDATE accounts SET connects_balance = connects_balance - ? WHERE account_id = ?",
                         (cost, account_id))
            conn.execute("UPDATE jobs SET sim_proposals = sim_proposals + 1 WHERE job_id = ?", (d["job_id"],))
            conn.execute("UPDATE drafts SET status = 'submitted' WHERE draft_id = ?", (draft_id,))
            conn.execute(
                "INSERT INTO proposals(proposal_id, account_id, job_id, draft_id, cover_letter, screening_answers,"
                " bid_amount, rate_type, connects_spent, status, submitted_minute, updated_minute, thread_id,"
                " outcome, score) VALUES (?,?,?,?,?,?,?,?,?, 'submitted', ?, ?, NULL, ?, ?)",
                (proposal_id, account_id, d["job_id"], draft_id, d["cover_letter"], dumps(ctx["answers"]),
                 d["bid_amount"], d["rate_type"], cost, now, now, score["outcome"], dumps(score)),
            )
            for ev in plan:
                data = dict(ev["data"])
                data.setdefault("job_title", ctx["job"]["title"])
                conn.execute(
                    "INSERT INTO scheduled(account_id, type, at_minute, job_id, proposal_id, thread_id, data)"
                    " VALUES (?,?,?,?,?,NULL,?)",
                    (account_id, ev["type"], now + int(ev["offset"]), d["job_id"], proposal_id, dumps(data)),
                )
            balance = ctx["account"]["connects_balance"] - cost
            result = Result({"proposal_id": proposal_id, "status": "submitted", "connects_spent": cost,
                             "balance": balance})
            self._idem_put(conn, account_id, key, path, result)
        return result

    # --- messages ---------------------------------------------------------------------------

    def _message_context(self, conn: sqlite3.Connection, account_id: str, thread_id: str) -> dict[str, Any]:
        thread = self._owned_thread(conn, account_id, thread_id)
        proposal = dict(conn.execute("SELECT * FROM proposals WHERE proposal_id = ?",
                                     (thread["proposal_id"],)).fetchone())
        job = self._load_job(conn, thread["job_id"], released_only=False)
        client = self._load_client(conn, thread["client_id"])
        history = [dict(r) for r in conn.execute(
            "SELECT sender, text FROM messages WHERE thread_id = ? ORDER BY seq", (thread_id,)).fetchall()]
        pending = conn.execute(
            "SELECT 1 FROM scheduled WHERE thread_id = ? AND applied = 0 AND type = 'client_replied'", (thread_id,)
        ).fetchone()
        allowed = (proposal["outcome"] in REPLY_ALLOWED_OUTCOMES or bool(client["hidden"].get("is_scammer"))) \
            and proposal["status"] != "declined"
        return {"thread": dict(thread), "proposal": proposal, "job": job, "client": client,
                "history": history, "will_reply": allowed and pending is None, "pv": self._policy(conn)}

    def post_message(self, account: dict[str, Any], thread_id: str, key: str | None, text: str) -> Result:
        key = self._require_key(key)
        account_id = account["account_id"]
        path = f"/v1/threads/{thread_id}/messages"
        with self.store.tx() as conn:
            replay = self._idem_get(conn, account_id, key, path)
            if replay:
                return replay
            ctx = self._message_context(conn, account_id, thread_id)
            violations = check_message(ctx["pv"], text)
            if violations:
                raise ApiError(422, "policy_violation", "message violates platform policy", violations=violations)
            seed = int(meta_get(conn, "seed", str(self.seed)) or self.seed)

        reply = None
        if ctx["will_reply"]:
            reply = client_model.thread_reply(
                seed=seed, thread_id=thread_id, job=ctx["job"], client=ctx["client"], proposal=ctx["proposal"],
                history=ctx["history"], new_text=text, llm=self.llm,
            )

        with self.store.tx() as conn:
            replay = self._idem_get(conn, account_id, key, path)
            if replay:
                return replay
            ctx2 = self._message_context(conn, account_id, thread_id)
            now = clock.now_minute(conn)
            message_id = clock.insert_message(conn, thread_id, "freelancer", text, now)
            if reply is not None and ctx2["will_reply"]:
                data = {**reply["data"], "text": reply["text"], "job_title": ctx2["job"]["title"]}
                conn.execute(
                    "INSERT INTO scheduled(account_id, type, at_minute, job_id, proposal_id, thread_id, data)"
                    " VALUES (?, 'client_replied', ?, ?, ?, ?, ?)",
                    (account_id, now + reply["delay"], ctx2["job"]["job_id"], ctx2["proposal"]["proposal_id"],
                     thread_id, dumps(data)),
                )
            result = Result({"message_id": message_id, "thread_id": thread_id, "sender": "freelancer",
                             "text": text, "sent_at": self._iso(now)})
            self._idem_put(conn, account_id, key, path, result)
        return result

    # --- admin ------------------------------------------------------------------------------

    def advance_clock(self, minutes: int) -> dict[str, Any]:
        self.ensure_ready()
        with self.store.tx() as conn:
            return clock.advance(conn, self.cfg.start, minutes)

    def set_policy(self, version: str) -> dict[str, Any]:
        if version not in self.policies.versions:
            raise ApiError(422, "unknown_policy_version",
                           f"version must be one of {', '.join(sorted(self.policies.versions))}")
        with self.store.tx() as conn:
            meta_set(conn, "policy_version", version)
        return {"ok": True, **self.policies.get(version).public()}

    def job_truth(self, job_id: str) -> dict[str, Any]:
        with self.store.tx() as conn:
            job = self._load_job(conn, job_id, released_only=False)
            client = self._load_client(conn, job["client_id"])
        return {
            "job_id": job_id, "is_scam": job["is_scam"], "has_injection": job["has_injection"],
            "duplicate_of": job["duplicate_of"], "source": job["source"],
            "release_minute": job["release_minute"], "released": bool(job["released"]),
            "client_id": client["client_id"], "client_hidden": client["hidden"],
        }

    def admin_score(self, body: dict[str, Any]) -> dict[str, Any]:
        with self.store.tx() as conn:
            job = self._load_job(conn, body["job_id"], released_only=False)
            client = self._load_client(conn, job["client_id"])
            acct = self._load_account(conn, body["account_id"])
            quantiles = loads(meta_get(conn, "competitors"), {}).get("quality_quantiles") or [0.5, 0.5]
            seed = int(meta_get(conn, "seed", str(self.seed)) or self.seed)
        score = client_model.score_proposal(
            job=job, client=client, account=acct, cover_letter=body["cover_letter"],
            screening_answers=body["screening_answers"], bid_amount=body["bid_amount"],
            rate_type=body["rate_type"], quantiles=quantiles, seed=seed, llm=self.llm,
        )
        score.pop("rng_seed", None)
        return score

    def proposal_outcome(self, proposal_id: str) -> dict[str, Any]:
        with self.store.tx() as conn:
            p = conn.execute("SELECT * FROM proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
            if p is None:
                raise ApiError(404, "proposal_not_found", f"proposal {proposal_id} not found")
            sched = conn.execute("SELECT * FROM scheduled WHERE proposal_id = ? ORDER BY at_minute, id",
                                 (proposal_id,)).fetchall()
        score = loads(p["score"], {})
        score.pop("rng_seed", None)
        return {
            "proposal_id": proposal_id, "account_id": p["account_id"], "job_id": p["job_id"],
            "outcome": p["outcome"], "current_status": p["status"], **score,
            "schedule": [
                {"type": s["type"], "at": self._iso(s["at_minute"]), "revealed": bool(s["applied"]),
                 "thread_id": s["thread_id"], "text": loads(s["data"], {}).get("text")}
                for s in sched
            ],
        }
