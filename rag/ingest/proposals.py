"""Past proposals per persona (~150 each) written for real K1 jobs outside the dev/held-out sets,
with outcomes from GigSim's stateless scorer (POST /admin/score).

Styles are assigned on purpose: ~45% specific (evidence-backed), ~25% generic opener, ~15% too long,
~15% short. Outcome mapping: hired/interview -> won, replied -> replied, everything else -> ignored.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import httpx

from rag.ingest.common import (GEN_MODELS, PERSONA_IDS, PERSONAS_DIR, PROCESSED, ROOT, generator, load_specs,
                               read_jsonl, stable_int, word_count, write_jsonl)
from rag.ingest.llm import chat_json, parse_json, print_session_usage

PV = "proposal_v1"
# a dedicated port + DB so labelling never collides with a dev GigSim seeded from fixtures
GIGSIM_URL = os.environ.get("GIGSIM_ADMIN_URL", "http://127.0.0.1:8091")
ADMIN = {"X-Admin-Token": os.environ.get("GIGSIM_ADMIN_TOKEN", "gigsim-admin")}
STYLE_SHARES = [("specific", 0.45), ("generic", 0.25), ("long", 0.15), ("short", 0.15)]
BATCH = {"specific": 4, "generic": 5, "long": 3, "short": 6}
WORDS = {"specific": (130, 260), "generic": (110, 230), "long": (380, 560), "short": (30, 75)}
STYLE_RULES = {
    "specific": ("Open with the client's actual problem (no greeting fluff). Cite one or two of the freelancer's past "
                 "projects from the list that genuinely match, with their real numbers. Name the tools you would use. "
                 "Propose a concrete first step and end with one sharp question."),
    "generic": ("Write the kind of template proposal freelancers paste everywhere. The FIRST sentence must be a stock "
                "opener such as 'I am writing to apply for your job', 'Dear Hiring Manager,', 'I am a highly skilled "
                "professional', 'I have read your job description carefully' or 'I am excited to apply'. Talk about "
                "yourself in general terms, no numbers, no specific past project, barely reference the job."),
    "long": ("Write an over-long, rambling proposal: restate the job at length, describe your whole background, list "
             "many tools, a detailed multi-phase plan and several paragraphs of reassurance. It may mention a past "
             "project. Do not be generic in the first sentence."),
    "short": ("Write a terse proposal of 2-4 sentences: one line on fit, maybe one past project, and availability. "
              "No greeting fluff."),
}
SYSTEM = ("You write freelancer proposals (cover letters) for a SYNTHETIC dataset used to study proposal quality. "
          "Write in the freelancer's voice. Never include email addresses, phone numbers, external links or "
          "messaging apps, never promise guarantees or refunds, never suggest working outside the platform. "
          "Reply with one JSON object only.")


def assign_styles(n: int, rng: random.Random) -> list[str]:
    counts = [round(n * s) for _, s in STYLE_SHARES]
    counts[0] += n - sum(counts)
    styles = [st for (st, _), c in zip(STYLE_SHARES, counts) for _ in range(c)]
    rng.shuffle(styles)
    return styles


def persona_evidence_text(p: dict) -> str:
    lines = []
    for x in p["projects"]:
        lines.append(f"- {x['title']} ({x['client']}, {x['date']}): {x['outcome']}. Tools: {', '.join(x['stack'])}")
    for g in p["minor_gigs"]:
        lines.append(f"- {g['title']} ({g['date']}): {g['outcome']}")
    return "\n".join(lines)


def bid_for(job: dict, p: dict, style: str, rng: random.Random) -> tuple[float, str]:
    if job.get("is_hourly"):
        rate = p["hourly_rate"] * rng.uniform(0.8, 1.05)
        hi = job.get("hourly_high") or job.get("hourly_low")
        if hi and rng.random() < 0.5:
            rate = min(rate, hi * rng.uniform(0.9, 1.15))
        return float(max(10, round(rate))), "hourly"
    budget = job.get("budget") or rng.choice([300, 500, 800, 1200])
    f = rng.uniform(0.8, 1.15) if style != "long" else rng.uniform(0.95, 1.35)
    return float(max(20, round(budget * f, -1) if budget >= 100 else round(budget * f))), "fixed"


def write_batch(pid: str, p: dict, style: str, jobs: list[dict], ev_text: str) -> tuple[dict, str, int]:
    lo, hi = WORDS[style]
    blocks = []
    alias = {f"J{i + 1}": j["job_id"] for i, j in enumerate(jobs)}   # models mangle "~01..." ids
    for i, j in enumerate(jobs):
        qs = j.get("screening_questions") or []
        blocks.append(f"### JOB J{i + 1}\nTitle: {j['title']}\nDescription: {' '.join(j['description'].split())[:900]}\n"
                      f"Bid: {j['_bid']} USD ({j['_rate_type']})\nScreening questions: {json.dumps(qs)}")
    user = (f"Freelancer: {p['name']}, {p['title']}, {p['years_experience']} years. Voice: {p['voice']}.\n"
            f"Past work the freelancer may cite (only these, never invent others):\n{ev_text}\n\n"
            f"STYLE for every proposal below: {style.upper()}. {STYLE_RULES[style]}\n"
            f"Cover letter length: {lo}-{hi} words. Screening answers: one answer per question, in the same style "
            f"({'concrete, 25-70 words' if style in ('specific', 'long') else 'brief and vague' if style == 'generic' else 'one short sentence'}).\n\n"
            + "\n\n".join(blocks)
            + '\n\nReturn JSON: {"proposals": [{"job": "J1", "cover_letter": "...", "screening_answers": ["..."]}]} '
              "with one entry per job, in the same order.")
    want = {f"J{i + 1}": len(j.get("screening_questions") or []) for i, j in enumerate(jobs)}

    def key(x: dict) -> str:
        return str(x.get("job") or x.get("job_id") or "").strip().upper().replace("JOB ", "")

    def ok(content: str) -> bool:
        d = parse_json(content)
        got = {key(x): x for x in d.get("proposals", [])}
        for jid, nq in want.items():
            x = got.get(jid)
            if not x or not isinstance(x.get("cover_letter"), str):
                return False
            wc = word_count(x["cover_letter"])
            if not (lo * 0.55 <= wc <= hi * 1.5):
                return False
            if not isinstance(x.get("screening_answers") or [], list):
                return False
            # fewer answers than questions is tolerated (padded with "" later, scored as unanswered)
        return True

    seed = stable_int(pid, style, *alias.values())
    data, res = chat_json(GEN_MODELS, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                          temperature=0.8, seed=seed, max_tokens=6000, validate=ok)
    return {alias[key(x)]: x for x in data["proposals"] if key(x) in alias}, res["model"], seed


# ------------------------------------------------------------------------------------- GigSim
def gigsim_up() -> bool:
    try:
        return httpx.get(f"{GIGSIM_URL}/health", timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


def start_gigsim() -> subprocess.Popen | None:
    if gigsim_up():
        print("  using the GigSim already running at", GIGSIM_URL)
        return None
    env = dict(os.environ)
    env.setdefault("GIGSIM_SEED_DIR", str(PROCESSED / "gigsim_seed"))
    env.setdefault("GIGSIM_DB", str(ROOT / "data" / "cache" / "gigsim_labels.sqlite"))
    env.setdefault("GIGSIM_ERROR_RATE", "0")
    # Score with GigSim's deterministic heuristic personalisation (no LLM): reproducible labels and no
    # contention with the Groq daily token caps. Set GIGSIM_LABEL_USE_LLM=1 to use the LLM rating instead.
    if os.environ.get("GIGSIM_LABEL_USE_LLM") != "1":
        env["GIGSIM_LLM_DISABLED"] = "1"
    port = GIGSIM_URL.rsplit(":", 1)[-1]
    log = open(ROOT / "data" / "cache" / "gigsim_labels.log", "w")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "gigsim.app:app", "--port", port, "--log-level", "warning"],
                            cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        if gigsim_up():
            print(f"  started GigSim (pid {proc.pid}) with seed {env['GIGSIM_SEED_DIR']}")
            return proc
        if proc.poll() is not None:
            raise SystemExit("GigSim failed to start; see data/cache/gigsim_labels.log")
        time.sleep(1)
    proc.terminate()
    raise SystemExit("GigSim did not become healthy in time")


def score(job_id: str, account_id: str, prop: dict) -> dict:
    body = {"job_id": job_id, "cover_letter": prop["cover_letter"], "screening_answers": prop["screening_answers"],
            "bid_amount": prop["bid_amount"], "rate_type": prop["rate_type"], "account_id": account_id}
    for attempt in range(6):
        r = httpx.post(f"{GIGSIM_URL}/admin/score", json=body, headers=ADMIN, timeout=90)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503) and attempt < 5:
            time.sleep(2 * (attempt + 1))
            continue
        raise RuntimeError(f"/admin/score {r.status_code}: {r.text[:300]}")
    raise RuntimeError("unreachable")


OUTCOME_MAP = {"hired": "won", "interview": "won", "replied": "replied"}


# ------------------------------------------------------------------------------------- main
def build(workers: int = 3) -> None:
    specs = load_specs()
    jobs_all = read_jsonl(PROCESSED / "past_proposal_jobs.jsonl")
    if not jobs_all:
        raise SystemExit("data/processed/past_proposal_jobs.jsonl missing: run scripts/build_dataset.py first")
    plan = []   # (pid, style, [jobs])
    per_pid: dict[str, list[dict]] = {}
    for pid in PERSONA_IDS:
        p = specs[pid]
        rng = random.Random(stable_int("proposals", pid))
        jobs = [j for j in jobs_all if j["persona_id"] == pid]
        styles = assign_styles(len(jobs), rng)
        for j, st in zip(jobs, styles):
            j["_style"] = st
            j["_bid"], j["_rate_type"] = bid_for(j, p, st, rng)
        per_pid[pid] = jobs
        for st in BATCH:
            sj = [j for j in jobs if j["_style"] == st]
            for i in range(0, len(sj), BATCH[st]):
                plan.append((pid, st, sj[i:i + BATCH[st]]))
    print(f"proposal generation: {sum(len(b) for _, _, b in plan)} proposals in {len(plan)} LLM calls", flush=True)
    written: dict[str, dict] = {}
    failed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(write_batch, pid, specs[pid], st, b, persona_evidence_text(specs[pid])): (pid, st, b)
                for pid, st, b in plan}
        for n, f in enumerate(as_completed(futs), 1):
            pid, st, b = futs[f]
            try:
                props, model, seed = f.result()
                for j in b:
                    written[f"{pid}|{j['job_id']}"] = dict(props[j["job_id"]], _model=model, _seed=seed)
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"  batch failed {pid}/{st}: {e!r}", flush=True)
            if n % 10 == 0:
                print(f"  {n}/{len(plan)} batches", flush=True)
    print_session_usage()
    if failed:
        # keep going with what exists (daily token caps); a rerun fills the gaps from the cache
        print(f"WARNING: {failed} proposal batches failed; writing the {len(written)} proposals that exist. "
              "Rerun scripts/label_proposals.py later to complete them.", flush=True)
        for pid in PERSONA_IDS:
            per_pid[pid] = [j for j in per_pid[pid] if f"{pid}|{j['job_id']}" in written]
        if not written:
            raise SystemExit("no proposals generated")

    proc = start_gigsim()
    try:
        probe = next(j["job_id"] for pid in PERSONA_IDS for j in per_pid[pid])
        r = httpx.get(f"{GIGSIM_URL}/admin/jobs/{probe}/truth", headers=ADMIN, timeout=10)
        if r.status_code != 200:
            raise SystemExit(f"GigSim at {GIGSIM_URL} does not know past-proposal job {probe} "
                             "(is it seeded from data/processed/gigsim_seed?)")
        tasks = []
        for pid in PERSONA_IDS:
            for j in per_pid[pid]:
                w = written[f"{pid}|{j['job_id']}"]
                nq = len(j.get("screening_questions") or [])
                answers = [str(a).strip() for a in (w.get("screening_answers") or [])][:nq]
                answers += [""] * (nq - len(answers))
                prop = {"cover_letter": w["cover_letter"].strip(),
                        "screening_answers": answers,
                        "bid_amount": j["_bid"], "rate_type": j["_rate_type"]}
                tasks.append((pid, j, w, prop))
        results = {}
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(score, j["job_id"], specs[pid]["gigsim_account_id"], prop): (pid, j["job_id"])
                    for pid, j, w, prop in tasks}
            for n, f in enumerate(as_completed(futs), 1):
                results[futs[f]] = f.result()
                if n % 100 == 0:
                    print(f"  scored {n}/{len(tasks)}", flush=True)
    finally:
        if proc is not None:
            proc.terminate()

    for pid in PERSONA_IDS:
        rows = []
        tasks_p = sorted([t for t in tasks if t[0] == pid], key=lambda t: (t[1].get("published_date") or "", t[1]["job_id"]))
        for n, (_, j, w, prop) in enumerate(tasks_p, start=1):
            s = results[(pid, j["job_id"])]
            pub = datetime.fromisoformat(j["published_date"])
            date = pub + timedelta(hours=1 + stable_int(pid, j["job_id"]) % 30)
            date = min(date, datetime.fromisoformat("2024-02-20T08:00:00+00:00"))
            rows.append({
                "evidence_id": f"{pid}:proposal:{n:03d}", "job_ref": j["job_id"], "job_title": j["title"],
                "job_excerpt": " ".join(j["description"].split())[:600], "cover_letter": prop["cover_letter"],
                "screening_questions": j.get("screening_questions") or [],
                "screening_answers": prop["screening_answers"], "bid_amount": prop["bid_amount"],
                "rate_type": prop["rate_type"], "date": date.strftime("%Y-%m-%d"),
                "outcome": OUTCOME_MAP.get(s["outcome"], "ignored"), "outcome_raw": s["outcome"],
                "outcome_source": "gigsim_admin_score", "p_reply": s.get("p_reply"), "p_hire": s.get("p_hire"),
                "score_components": s.get("components"), "style": j["_style"], "category": j["category"],
                "word_count": word_count(prop["cover_letter"]), "synthetic": True,
                "generator": generator(w["_model"], PV, w["_seed"]),
            })
        write_jsonl(PERSONAS_DIR / pid / "proposals.jsonl", rows)
        # refresh the proposal rows of the persona index
        idx_path = PERSONAS_DIR / pid / "index.jsonl"
        idx = [x for x in read_jsonl(idx_path) if x["type"] != "proposal"]
        for r in rows:
            idx.append({"evidence_id": r["evidence_id"], "type": "proposal", "title": f"Proposal: {r['job_title']}",
                        "project_slug": None, "date": r["date"], "path": "proposals.jsonl",
                        "summary": f"{r['style']} proposal, outcome {r['outcome']}. " + r["cover_letter"][:140],
                        "off_niche": False})
        write_jsonl(idx_path, idx)
        oc = Counter(r["outcome"] for r in rows)
        by_style = {st: Counter(r["outcome"] for r in rows if r["style"] == st) for st in BATCH}
        print(f"{pid}: {len(rows)} proposals, outcomes {dict(oc)}")
        for st, c in by_style.items():
            tot = sum(c.values()) or 1
            print(f"    {st:8s} n={tot:3d} won={c['won']/tot:.2f} replied={c['replied']/tot:.2f}")
