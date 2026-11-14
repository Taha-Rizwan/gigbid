"""Shared plumbing for the eval runners.

- Paths, dataset loading, result headers ({generated_at, git_sha_or_null, config_snapshot, n}).
- A disk cache for every LLM call made through agent.llm (structured / text) and for Prompt Guard,
  so nothing is computed twice. Cache hits replay the stored token counts into the run's Usage
  (so tokens / cost stay attributable) and are counted, so latency is only reported for cold runs.
- A per-model throttle (tokens per minute, concurrency) and 429 handling with backoff. A daily
  quota error raises DailyLimitReached, which runners catch to write partial results.
- A per-record cache: each runner stores one finished record per (job, setting), so a rerun only
  computes what is missing and keeps the latency measured the first time.
"""

from __future__ import annotations

import asyncio
import collections
import contextvars
import csv
import datetime as dt
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

RESULTS_DIR = ROOT / "evals" / "results"
DATASETS_DIR = ROOT / "evals" / "datasets"
CACHE_DIR = ROOT / "data" / "cache" / "evals"
PERSONAS = ["ai_ml", "fullstack", "data_analyst"]
DEFAULT_GIGSIM = "http://localhost:8091"
ADMIN_TOKEN = os.environ.get("GIGSIM_ADMIN_TOKEN", "gigsim-admin")

log = logging.getLogger("gigbid.evals")


class DailyLimitReached(RuntimeError):
    """A provider's daily request/token quota is exhausted. Runners stop and write partial results."""


# ----------------------------------------------------------------------------- env / args

def setup(gigsim_url: str | None = None) -> str:
    """Point the marketplace adapter at the eval GigSim (process env only)."""
    import common  # noqa: F401  (Windows event loop policy)

    url = gigsim_url or os.environ.get("EVAL_GIGSIM_URL") or DEFAULT_GIGSIM
    os.environ["GIGSIM_BASE_URL"] = url
    os.environ.setdefault("LANGSMITH_TRACING", "false")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for noisy in ("bm25s", "httpx", "mcp", "fastembed"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return url


def add_common_args(ap) -> None:
    ap.add_argument("--persona", default="all", help="ai_ml | fullstack | data_analyst | all")
    ap.add_argument("--limit", type=int, default=None, help="max jobs per persona")
    ap.add_argument("--dataset-dir", default=str(DATASETS_DIR))
    ap.add_argument("--out-dir", default=str(RESULTS_DIR))
    ap.add_argument("--gigsim", default=None, help=f"GigSim base URL (default {DEFAULT_GIGSIM})")
    ap.add_argument("--profile", default="paid", help="model profile (paid | open | open_alt); default paid")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--tag", default="", help="suffix for the output file name (smoke runs etc.)")


def personas_arg(p: str) -> list[str]:
    return PERSONAS if p in (None, "", "all") else [x.strip() for x in p.split(",") if x.strip()]


def git_sha() -> str | None:
    """Read .git/HEAD directly (no git subprocess). None when not a repository."""
    head = ROOT / ".git" / "HEAD"
    try:
        ref = head.read_text().strip()
        if ref.startswith("ref:"):
            p = ROOT / ".git" / ref.split(" ", 1)[1]
            if p.exists():
                return p.read_text().strip()
            packed = ROOT / ".git" / "packed-refs"
            for line in packed.read_text().splitlines():
                if line.endswith(ref.split(" ", 1)[1]):
                    return line.split()[0]
            return None
        return ref
    except OSError:
        return None


# ----------------------------------------------------------------------------- data

def load_jsonl(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def load_dev(personas: list[str], limit: int | None = None, dataset_dir: str | Path = DATASETS_DIR,
             where=None) -> list[dict]:
    """Dev jobs in file order, filtered by `where(row)`, at most `limit` per persona."""
    out = []
    for p in personas:
        rows = load_jsonl(Path(dataset_dir) / f"dev_{p}.jsonl")
        rows = [r for r in rows if where is None or where(r)]
        out += rows[:limit] if limit else rows
    return out


def gold_labelled(row: dict) -> bool:
    """True once the dataset agent has written LLM gold for this row."""
    g = row.get("gold") or {}
    return bool(g.get("relevant_evidence_ids") or g.get("label_model") or g.get("requirements"))


def seed_accounts() -> dict[str, dict]:
    seed = Path(os.environ.get("GIGSIM_SEED_DIR", ROOT / "data" / "processed" / "gigsim_seed")) / "accounts.jsonl"
    rows = load_jsonl(seed) or load_jsonl(ROOT / "gigsim" / "fixtures" / "accounts.jsonl")
    default = {"acct_ai": "ai_ml", "acct_web": "fullstack", "acct_data": "data_analyst"}
    return {r.get("persona_id") or default.get(r["account_id"]): r for r in rows}


def persona_profile(persona: str) -> dict:
    """The user profile the graph gets (floors from scripts/persona_specs.yaml, as in LABELING.md)."""
    floors = {}
    spec = ROOT / "scripts" / "persona_specs.yaml"
    try:
        import yaml

        data = yaml.safe_load(spec.read_text(encoding="utf-8")) or {}
        items = data.get("personas", data)
        for k, v in (items.items() if isinstance(items, dict) else []):
            if isinstance(v, dict) and "floor_rate" in v:
                floors[k] = float(v["floor_rate"])
    except Exception:  # noqa: BLE001
        pass
    floor = floors.get(persona, {"ai_ml": 40, "fullstack": 35, "data_analyst": 28}.get(persona, 35))
    return {"hourly_floor": floor, "fixed_floor": 150, "weekly_connects_budget": 400}


def row_job(row: dict):
    """A Job built from a dev row the same way intake builds it from get_job (None fields dropped)."""
    from agent.handoffs import Job

    return Job(**{k: v for k, v in row.items() if k in Job.model_fields and k != "source" and v is not None},
               source="gigsim")


# ----------------------------------------------------------------------------- results

def model_snapshot(profile: str | None = None) -> dict:
    from agent.settings import config

    cfg = config()
    prof = profile or cfg["models"]["profile"]
    return {"profile": prof, "tiers": cfg["models"]["profiles"][prof], "nodes": cfg["models"]["nodes"],
            "embeddings": cfg["models"]["embeddings"], "reranker": cfg["models"]["reranker"]}


def header(runner: str, args, n: int, extra: dict | None = None, profile: str | None = None) -> dict:
    from agent.settings import config

    cfg = config()
    snap = {
        "runner": runner,
        "args": {k: v for k, v in vars(args).items() if k not in ("out_dir", "dataset_dir")} if args else {},
        "models": model_snapshot(profile or (getattr(args, "profile", None) if args else None)),
        "rag": dict(cfg["rag"]),
        "thresholds": dict(cfg["thresholds"]),
        "budgets": {k: cfg["budgets"][k] for k in ("max_tokens_per_job", "max_revisions", "max_graph_steps")},
        "policy_version": cfg["policy"]["version"],
        "gigsim": {"base_url": os.environ.get("GIGSIM_BASE_URL"), "seed_dir": "data/processed/gigsim_seed",
                   "error_rate": 0, "rate_per_min": 0,
                   "personalisation": "heuristic fallback (GIGSIM_LLM_DISABLED=1) to save Groq quota; deterministic"},
        "llm_cache": "data/cache/evals/llm (hits replay stored token counts; latency only from cold runs)",
    } | (extra or {})
    return {"generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "git_sha_or_null": git_sha(),
            "config_snapshot": snap, "n": n}


def write_json(name: str, obj: dict, out_dir: str | Path = RESULTS_DIR) -> Path:
    from evals.metrics import rounded

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / name
    p.write_text(json.dumps(rounded(obj), indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {p}")
    return p


def write_csv(name: str, rows: list[dict], out_dir: str | Path = RESULTS_DIR) -> Path | None:
    if not rows:
        return None
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / name
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    print(f"wrote {p}")
    return p


def latency_stats(records: list[dict], key: str = "latency_s") -> dict:
    """p50/p95 over cold records only (no LLM cache hits), with the n they come from."""
    from evals.metrics import percentile

    cold = [r[key] for r in records if r.get(key) is not None and not r.get("llm_cache_hits")]
    return {"p50_s": percentile(cold, 50), "p95_s": percentile(cold, 95), "n_cold": len(cold),
            "n_total": len(records)}


def usage_stats(records: list[dict]) -> dict:
    from evals.metrics import mean

    us = [r.get("usage") or {} for r in records if r.get("usage")]
    return {"tokens_mean": mean([u.get("tokens") for u in us]), "cost_usd_mean": mean([u.get("cost_usd") for u in us]),
            "llm_calls_mean": mean([u.get("calls") for u in us]),
            "tokens_total": sum(u.get("tokens", 0) for u in us), "cost_usd_total": sum(u.get("cost_usd", 0) for u in us),
            "n": len(us)}


# ----------------------------------------------------------------------------- record cache

class RecordCache:
    """One JSON file per finished record under data/cache/evals/records/<runner>/."""

    def __init__(self, runner: str):
        self.dir = CACHE_DIR / "records" / runner
        self.dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(*parts: Any) -> str:
        return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:40]

    def get(self, key: str) -> dict | None:
        p = self.dir / f"{key}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def put(self, key: str, rec: dict) -> dict:
        (self.dir / f"{key}.json").write_text(json.dumps(rec, default=str, ensure_ascii=False), encoding="utf-8")
        return rec


# ----------------------------------------------------------------------------- LLM cache + throttle

cache_stats: contextvars.ContextVar[dict | None] = contextvars.ContextVar("eval_cache_stats", default=None)
_LLM_CACHE = CACHE_DIR / "llm"
_window: dict[str, collections.deque] = collections.defaultdict(collections.deque)
_sems: dict[str, asyncio.Semaphore] = {}
_tlock: asyncio.Lock | None = None
TPM_BUDGET = int(os.environ.get("EVAL_TPM_BUDGET", "7000"))
CONCURRENCY = int(os.environ.get("EVAL_MODEL_CONCURRENCY", "2"))
_installed = False
_exhausted: dict[str, str] = {}


def _bump(field: str) -> None:
    s = cache_stats.get()
    if s is not None:
        s[field] = s.get(field, 0) + 1


def _msg_key(messages) -> list:
    return [[getattr(m, "type", "?"), m.content if isinstance(m.content, str) else json.dumps(m.content, default=str)]
            for m in messages]


def _cache_path(key: str) -> Path:
    _LLM_CACHE.mkdir(parents=True, exist_ok=True)
    return _LLM_CACHE / f"{key[:2]}" / f"{key}.json"


def _cache_get(key: str) -> dict | None:
    p = _cache_path(key)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _cache_put(key: str, entry: dict) -> None:
    p = _cache_path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entry, default=str, ensure_ascii=False), encoding="utf-8")


def _retry_after(msg: str) -> float:
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)(ms|s)", msg)
    if not m:
        return 20.0
    mins = float(m.group(1) or 0)
    secs = float(m.group(2)) / (1000 if m.group(3) == "ms" else 1)
    return mins * 60 + secs


async def _throttle(model: str, est_tokens: int) -> None:
    """Wait until this model's own usage in the last 60 s leaves room for est_tokens."""
    global _tlock
    if _tlock is None:
        _tlock = asyncio.Lock()
    if "claude" in model:
        return
    while True:
        async with _tlock:
            now = time.monotonic()
            w = _window[model]
            while w and now - w[0][0] > 60:
                w.popleft()
            used = sum(t for _, t in w)
            if used + est_tokens <= TPM_BUDGET or not w:
                w.append((now, est_tokens))
                return
            wait = 60 - (now - w[0][0]) + 0.5
        await asyncio.sleep(max(1.0, wait))


def _settle(model: str, est: int, actual: int) -> None:
    w = _window[model]
    for i in range(len(w) - 1, -1, -1):
        if w[i][1] == est:
            w[i] = (w[i][0], actual)
            return


ANTHROPIC_CAP_USD = float(os.environ.get("EVAL_ANTHROPIC_CAP_USD", "4.0"))
_SPEND_LOG = CACHE_DIR / "anthropic_spend.jsonl"


def anthropic_spend() -> float:
    """Total Anthropic spend by all eval runners (append-only ledger shared across processes)."""
    if not _SPEND_LOG.exists():
        return 0.0
    return sum(json.loads(x)["cost_usd"] for x in _SPEND_LOG.read_text(encoding="utf-8").splitlines() if x.strip())


def _log_spend(model: str, node: str, cost: float) -> None:
    _SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(_SPEND_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "model": model,
                            "node": node, "cost_usd": cost}) + "\n")


MAX_QUOTA_WAIT = float(os.environ.get("EVAL_MAX_QUOTA_WAIT", "900"))


async def call_with_backoff(model: str, est_tokens: int, fn, max_attempts: int = 40):
    """Throttle, run fn(), and retry rate limits. Groq's daily quotas are rolling windows: when the
    suggested wait is short we sleep and retry; otherwise raise DailyLimitReached."""
    if model in _exhausted:
        raise DailyLimitReached(_exhausted[model])
    sem = _sems.setdefault(model, asyncio.Semaphore(CONCURRENCY * (3 if "claude" in model else 1)))
    for attempt in range(max_attempts):
        await _throttle(model, est_tokens)
        try:
            async with sem:
                return await fn()
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            low = msg.lower()
            if "per day" in low or "(rpd)" in low or "(tpd)" in low:
                wait = _retry_after(msg)
                if wait <= MAX_QUOTA_WAIT and attempt < max_attempts - 1:
                    log.warning("daily quota on %s; rolling window frees room in %.0fs, waiting", model, wait)
                    await asyncio.sleep(wait + 5 + random.random() * 5)
                    continue
                _exhausted[model] = f"daily quota exhausted for {model}: {msg[msg.find('Rate limit'):][:260]}"
                raise DailyLimitReached(_exhausted[model]) from None
            if "429" in msg or "rate_limit" in low or "rate limit" in low or "overloaded" in low or "503" in msg:
                wait = min(90.0, _retry_after(msg) + random.random() * 2 + attempt * 2)
                log.warning("rate limited on %s (attempt %d); sleeping %.1fs", model, attempt + 1, wait)
                await asyncio.sleep(wait)
                continue
            raise
    raise RuntimeError(f"gave up on {model} after {max_attempts} rate-limited attempts")


def install_llm_cache() -> None:
    """Monkeypatch agent.llm.structured / text and the Prompt Guard call with cached, throttled
    versions. Graph semantics are unchanged: the same prompts go to the same models."""
    global _installed
    if _installed:
        return
    _installed = True
    from agent import guardrails
    from agent import llm as L
    from agent.settings import model_spec

    orig_structured, orig_text, orig_pg = L.structured, L.text, guardrails.prompt_guard_score
    orig_get_model = L.get_model
    used_model: contextvars.ContextVar[list | None] = contextvars.ContextVar("eval_used_model", default=None)

    def get_model(node, profile=None):
        m, name = orig_get_model(node, profile)
        box = used_model.get()
        if box is not None:
            box.append(name)
        return m, name

    L.get_model = get_model

    def merge(outer, node: str, model: str, inp: int, out: int, cost: float, seconds: float) -> None:
        outer.calls += 1
        outer.input_tokens += inp
        outer.output_tokens += out
        outer.cost_usd += cost
        outer.latency_s += seconds
        nd = outer.by_node[node]
        nd["calls"] += 1
        nd["tokens"] += inp + out
        nd["cost_usd"] += cost

    def spec_of(node: str) -> dict:
        return model_spec(node, L.current_profile.get())

    async def run_cached(kind: str, node: str, payload: dict, call, decode):
        spec = spec_of(node)
        key = hashlib.sha256(json.dumps({"kind": kind, "node": node, "spec": spec, **payload},
                                        sort_keys=True, default=str).encode()).hexdigest()
        outer = L.current_usage.get()
        hit = _cache_get(key)
        if hit is not None:
            _bump("llm_cache_hits")
            if outer is not None:
                merge(outer, node, hit["model"], hit["input_tokens"], hit["output_tokens"],
                      hit.get("cost_usd", 0.0), hit.get("latency_s", 0))
                _check_cap(outer)
            return decode(hit["value"])
        _bump("llm_calls_cold")
        if "claude" in spec["model"] and anthropic_spend() >= ANTHROPIC_CAP_USD:
            _exhausted[spec["model"]] = f"eval Anthropic budget cap reached (${ANTHROPIC_CAP_USD})"
            raise DailyLimitReached(_exhausted[spec["model"]])
        tmp = L.Usage()
        est = int(sum(len(c) for _, c in payload.get("messages", [])) / 3.5) + 1500
        t0 = time.perf_counter()

        models_used: list[str] = []

        async def once():
            models_used.clear()
            token, token2 = L.current_usage.set(tmp), used_model.set(models_used)
            try:
                return await call()
            finally:
                L.current_usage.reset(token)
                used_model.reset(token2)

        value = await call_with_backoff(spec["model"], est, once)
        _settle(spec["model"], est, tmp.tokens or est)
        entry = {"model": models_used[-1] if models_used else spec["model"], "requested_model": spec["model"],
                 "node": node, "input_tokens": tmp.input_tokens, "cost_usd": tmp.cost_usd,
                 "output_tokens": tmp.output_tokens, "latency_s": round(time.perf_counter() - t0, 3),
                 "value": value.model_dump(mode="json") if hasattr(value, "model_dump") else value,
                 "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
        _cache_put(key, entry)
        if "claude" in entry["model"]:
            _log_spend(entry["model"], node, tmp.cost_usd)
        if outer is not None:
            merge(outer, node, entry["model"], tmp.input_tokens, tmp.output_tokens, tmp.cost_usd, entry["latency_s"])
            _check_cap(outer)
        return value

    def _check_cap(usage) -> None:
        from agent.settings import config

        cap = config()["budgets"]["max_tokens_per_job"]
        if usage.tokens > cap:
            raise L.BudgetExceeded(f"token budget exceeded: {usage.tokens} > {cap}")

    async def structured(node, schema, messages):
        payload = {"schema": schema.__name__, "schema_json": schema.model_json_schema(), "messages": _msg_key(messages)}
        return await run_cached("structured", node, payload, lambda: orig_structured(node, schema, messages),
                                lambda v: schema.model_validate(v))

    async def text(node, messages):
        payload = {"messages": _msg_key(messages)}
        return await run_cached("text", node, payload, lambda: orig_text(node, messages), lambda v: v)

    async def prompt_guard_score(t: str):
        key = hashlib.sha256(f"promptguard|{t[:2000]}".encode()).hexdigest()
        hit = _cache_get(key)
        if hit is not None:
            return hit["value"]
        v = await orig_pg(t)
        if v is not None:  # do not cache "unavailable"
            _cache_put(key, {"model": "prompt_guard", "value": v, "input_tokens": 0, "output_tokens": 0})
        return v

    L.structured, L.text, guardrails.prompt_guard_score = structured, text, prompt_guard_score


def exhausted_models() -> dict[str, str]:
    return dict(_exhausted)


# ----------------------------------------------------------------------------- graph plumbing

class Harness:
    """In-process graph + in-memory MCP sessions. Personas run one at a time because the marketplace
    adapter (and so the GigSim account) is per process user."""

    def __init__(self):
        self.stack = None
        self.box = None
        self.saver = self.store = None

    async def __aenter__(self):
        from contextlib import AsyncExitStack

        from agent.mcp_client import ToolBox
        from agent.memory.store import open_persistence

        install_llm_cache()
        self.stack = AsyncExitStack()
        await self.stack.__aenter__()
        self.saver, self.store = await open_persistence(self.stack, durable=False)
        self.box = await ToolBox.in_memory(self.stack)
        return self

    async def __aexit__(self, *exc):
        await self.stack.__aexit__(*exc)

    def graph(self, interrupt_before: list[str] | None = None):
        """The real bid graph; optionally recompiled from its own builder with an extra interrupt."""
        from agent.graphs import bid_graph

        g = bid_graph.build(self.saver, self.store)
        if interrupt_before:
            g = g.builder.compile(checkpointer=self.saver, store=self.store, interrupt_before=interrupt_before)
        return g

    @staticmethod
    def use_persona(persona: str) -> None:
        from mcp_servers.marketplace import server as ms

        acct = seed_accounts().get(persona) or {}
        os.environ["GIGSIM_DEFAULT_TOKEN"] = acct.get("token") or "gigsim-token-ai"
        ms._adapters.clear()

    def ctx(self, datamark: bool = False, prompt_guard: bool = True):
        import uuid

        from agent.context import RunContext
        from agent.llm import Usage

        return RunContext(toolbox=self.box, usage=Usage(), trace_id=uuid.uuid4().hex, datamark=datamark,
                          prompt_guard=prompt_guard)


async def run_bid(h: Harness, graph, row: dict, persona: str, tag: str, profile_name: str | None = None,
                  datamark: bool = False, prompt_guard: bool = True) -> dict:
    """Run the bid graph for one job until END or an interrupt. Returns the runner output plus
    cache stats. Never resumes past the approval interrupt (nothing is submitted)."""
    import uuid

    from agent.runner import start_bid

    stats = {"llm_cache_hits": 0, "llm_calls_cold": 0}
    tok = cache_stats.set(stats)
    try:
        ctx = h.ctx(datamark=datamark, prompt_guard=prompt_guard)
        t0 = time.perf_counter()
        out = await start_bid(graph, "eval-user", persona, row["job_id"], persona_profile(persona), ctx,
                              thread_id=f"eval-{tag}-{row['job_id']}-{uuid.uuid4().hex[:6]}",
                              profile_name=profile_name)
        out["wall_s"] = round(time.perf_counter() - t0, 3)
    finally:
        cache_stats.reset(tok)
    out.update(stats)
    return out


async def admin_score(base_url: str, job_id: str, letter: str, answers: list[str], bid: float, rate_type: str,
                      account_id: str) -> dict:
    """GigSim's stateless, deterministic client model (POST /admin/score)."""
    import httpx

    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{base_url}/admin/score", headers={"X-Admin-Token": ADMIN_TOKEN},
                         json={"job_id": job_id, "cover_letter": letter, "screening_answers": answers,
                               "bid_amount": bid, "rate_type": rate_type, "account_id": account_id})
        r.raise_for_status()
        return r.json()


REPLY_OUTCOMES = {"replied", "interview", "hired"}


async def gather_bounded(coros, limit: int):
    sem = asyncio.Semaphore(limit)

    async def one(c):
        async with sem:
            return await c

    return await asyncio.gather(*(one(c) for c in coros), return_exceptions=True)


def run(main_coro) -> None:
    import common  # noqa: F401

    asyncio.run(main_coro)


# ----------------------------------------------------------------------------- sampling / keys

def sample_rows(rows: list[dict], n: int | None, seed: int = 42, where=None) -> list[dict]:
    """Deterministic per-persona sample (seeded shuffle), so every runner sees the same jobs."""
    by_p: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        if where is None or where(r):
            by_p[r["persona_id"]].append(r)
    out = []
    for p, rs in by_p.items():
        rs = sorted(rs, key=lambda r: r["job_id"])
        random.Random(f"{seed}-{p}").shuffle(rs)
        out += rs[:n] if n else rs
    return out


def settings_hash(profile: str | None = None, extra: Any = None) -> str:
    """Changes when prompts, the model profile, rag settings, thresholds or policy change."""
    from agent.settings import PROMPTS_DIR, config

    cfg = config()
    prof = profile or cfg["models"]["profile"]
    h = hashlib.sha256()
    for f in sorted(PROMPTS_DIR.glob("*.md")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    h.update(json.dumps([cfg["models"]["profiles"][prof], cfg["models"]["nodes"], cfg["rag"], cfg["thresholds"],
                         cfg["policy"], cfg["budgets"], extra], sort_keys=True, default=str).encode())
    return h.hexdigest()[:16]


def set_rag_variant(variant: str | None) -> str:
    """In-process config override of rag.variant (agent/config.yaml is never edited)."""
    from agent.settings import config

    if variant:
        config()["rag"]["variant"] = variant
    return config()["rag"]["variant"]


def dump(v: Any) -> Any:
    if hasattr(v, "model_dump"):
        return v.model_dump(mode="json")
    if isinstance(v, list):
        return [dump(x) for x in v]
    if isinstance(v, dict):
        return {k: dump(x) for k, x in v.items()}
    return v


def use_profile(profile: str | None) -> str:
    """Set the model profile for everything run from the current task (agent.llm.current_profile)."""
    from agent.llm import current_profile
    from agent.settings import config

    p = profile or config()["models"]["profile"]
    current_profile.set(p)
    return p
