"""Validate the data layer against docs/specs/DATA_SPEC.md and GIGSIM_SPEC.md; print a count table.

Checks: required fields per file, evidence ids in gold labels exist in the persona corpus, case-study
front matter and word counts, repo/review/proposal counts, GigSim seed referential integrity, and that
nothing under data/raw or data/processed escapes .gitignore. Exit code 1 on any failure.
"""
import fnmatch
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rag.ingest.common import (  # noqa: E402
    EVALS_DIR,
    PERSONA_IDS,
    PERSONAS_DIR,
    PROCESSED,
    read_jsonl,
    word_count,
)

ERR: list[str] = []
COUNTS: list[tuple[str, int, str]] = []


def need(rows, fields, name):
    for i, r in enumerate(rows):
        miss = [f for f in fields if f not in r]
        if miss:
            ERR.append(f"{name} row {i}: missing {miss}")
            return


def count(name, n, note=""):
    COUNTS.append((name, n, note))


def personas() -> dict[str, set]:
    ids = {}
    for pid in PERSONA_IDS:
        d = PERSONAS_DIR / pid
        prof = json.loads((d / "profile.json").read_text(encoding="utf-8"))
        need([prof], ["persona_id", "name", "title", "hourly_rate", "skills", "years_experience", "industries", "bio",
                      "gigsim_account_id", "synthetic", "generator"], f"{pid}/profile.json")
        for f in ("cv.md", "cv.pdf"):
            if not (d / f).exists():
                ERR.append(f"{pid}: {f} missing")
        cases = sorted((d / "case_studies").glob("*.md"))
        if not 15 <= len(cases) <= 25:
            ERR.append(f"{pid}: {len(cases)} case studies (want 15-25)")
        ev = {f"{pid}:cv:main"}
        for c in cases:
            txt = c.read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---\n(.*)$", txt, re.S)
            if not m:
                ERR.append(f"{c}: no front matter")
                continue
            fm = yaml.safe_load(m.group(1))
            need([fm], ["evidence_id", "title", "project", "client_industry", "date", "skills", "outcome", "synthetic"], str(c.name))
            wc = word_count(m.group(2))
            if not 230 <= wc <= 760:
                ERR.append(f"{c.name}: body {wc} words")
            ev.add(fm["evidence_id"])
        repos = [r for r in (d / "repos").iterdir() if r.is_dir()]
        if not 4 <= len(repos) <= 6:
            ERR.append(f"{pid}: {len(repos)} repos")
        vague = 0
        for r in repos:
            meta = json.loads((r / ".evidence.json").read_text(encoding="utf-8"))
            ev.add(meta["evidence_id"])
            vague += meta["vague_readme"]
            if not (r / "README.md").exists() or not [p for p in r.rglob("*") if p.is_file() and p.suffix in (".py", ".ts", ".sql", ".tsx", ".js")]:
                ERR.append(f"{r}: missing README or code")
        if vague < 2:
            ERR.append(f"{pid}: only {vague} vague-README repos")
        reviews = read_jsonl(d / "reviews.jsonl")
        need(reviews, ["evidence_id", "client_name", "project", "rating", "text", "date"], f"{pid}/reviews.jsonl")
        if not 10 <= len(reviews) <= 20:
            ERR.append(f"{pid}: {len(reviews)} reviews")
        ev |= {r["evidence_id"] for r in reviews}
        props = read_jsonl(d / "proposals.jsonl")
        need(props, ["evidence_id", "job_ref", "job_title", "job_excerpt", "cover_letter", "screening_answers", "bid_amount",
                     "rate_type", "date", "outcome", "outcome_source", "style", "synthetic"], f"{pid}/proposals.jsonl")
        for p in props:
            if len(p["job_excerpt"]) > 600 or p["outcome"] not in ("won", "replied", "ignored") or p["style"] not in ("specific", "generic", "long", "short"):
                ERR.append(f"{p['evidence_id']}: bad excerpt/outcome/style")
                break
        ev |= {p["evidence_id"] for p in props}
        idx = {x["evidence_id"] for x in read_jsonl(d / "index.jsonl")}
        if idx != ev:
            ERR.append(f"{pid}: index.jsonl differs from corpus ({len(idx ^ ev)} ids)")
        ids[pid] = ev
        oc = Counter(p["outcome"] for p in props)
        count(f"personas/{pid}/case_studies", len(cases))
        count(f"personas/{pid}/repos", len(repos), f"{vague} vague README")
        count(f"personas/{pid}/reviews.jsonl", len(reviews))
        count(f"personas/{pid}/proposals.jsonl", len(props), f"won={oc['won']} replied={oc['replied']} ignored={oc['ignored']}")
    return ids


GOLD = ["is_scam", "is_scam_source", "has_injection", "bid_or_skip", "bid_or_skip_source", "relevant_evidence_ids",
        "relevant_evidence_source", "fair_price_band", "fair_price_source", "required_skills", "required_skills_source",
        "requirement_count"]
JOB = ["job_id", "persona_id", "title", "description", "category", "is_hourly", "hourly_low", "hourly_high", "budget",
       "country", "gold"]


def evalsets(ev_ids: dict[str, set], gigsim_ids: set):
    for pid in PERSONA_IDS:
        rows = read_jsonl(EVALS_DIR / f"dev_{pid}.jsonl")
        need(rows, JOB, f"dev_{pid}")
        need([r["gold"] for r in rows], GOLD, f"dev_{pid} gold")
        bad = [e for r in rows for e in r["gold"]["relevant_evidence_ids"] if e not in ev_ids[pid]]
        if bad:
            ERR.append(f"dev_{pid}: {len(bad)} unknown evidence ids, e.g. {bad[:3]}")
        if len(rows) != 200:
            ERR.append(f"dev_{pid}: {len(rows)} rows")
        missing_seed = [r["job_id"] for r in rows if r["job_id"] not in gigsim_ids]
        if missing_seed:
            ERR.append(f"dev_{pid}: {len(missing_seed)} jobs not in the GigSim seed")
        unlabeled = sum(1 for r in rows if not r["gold"].get("label_model"))
        n_bad = sum(r["gold"]["is_scam"] or r["gold"]["has_injection"] for r in rows)
        n_bid = sum(r["gold"]["bid_or_skip"] == "bid" for r in rows)
        n_ev = sum(1 for r in rows if r["gold"]["relevant_evidence_ids"])
        st = Counter(r.get("stratum") for r in rows)
        count(f"evals/dev_{pid}.jsonl", len(rows), f"core/adj/unrel={st['core']}/{st['adjacent']}/{st['unrelated']} "
              f"scam+inj={n_bad} bid={n_bid} with_evidence={n_ev} unlabeled={unlabeled}")
    ho = read_jsonl(PROCESSED / "heldout_jobs.jsonl")
    need(ho, JOB, "heldout")
    for r in ho:
        bad = [e for e in r["gold"]["relevant_evidence_ids"] if e not in ev_ids[r["persona_id"]]]
        if bad:
            ERR.append(f"heldout {r['job_id']}: unknown evidence ids {bad}")
            break
    count("processed/heldout_jobs.jsonl", len(ho), "K1=%d K3=%d" % (sum(r["source"].startswith("kaggle_k1") for r in ho),
                                                                      sum(r["source"].startswith("kaggle_k3") for r in ho)))
    hc = read_jsonl(EVALS_DIR / "human_check.jsonl")
    need(hc, JOB, "human_check")
    count("evals/human_check.jsonl", len(hc))
    k3 = read_jsonl(EVALS_DIR / "k3_skills_eval.jsonl")
    need(k3, ["job_id", "title", "description", "skill_tags"], "k3_skills_eval")
    count("evals/k3_skills_eval.jsonl", len(k3))
    k6 = read_jsonl(PROCESSED / "k6_scam_eval.jsonl")
    need(k6, ["text", "is_fake"], "k6_scam_eval")
    count("processed/k6_scam_eval.jsonl", len(k6), f"fake={sum(r['is_fake'] for r in k6)}")
    if (EVALS_DIR / "k6_scam_eval.jsonl").exists():
        ERR.append("K6 data must not live under evals/ (never committed)")


def seed() -> set:
    d = PROCESSED / "gigsim_seed"
    jobs = read_jsonl(d / "jobs.jsonl")
    clients = read_jsonl(d / "clients.jsonl")
    accts = read_jsonl(d / "accounts.jsonl")
    need(jobs, ["job_id", "title", "description", "category", "skills", "is_hourly", "hourly_low", "hourly_high", "budget",
                "country", "client_id", "release_minute", "proposals_count", "screening_questions", "experience_level",
                "is_scam", "has_injection", "duplicate_of", "source"], "seed jobs")
    need(clients, ["client_id", "name", "country", "member_since", "total_spent", "jobs_posted", "hires", "avg_rating",
                   "payment_verified", "reviews", "hidden"], "seed clients")
    need([c["hidden"] for c in clients], ["must_have_skills", "budget_ceiling_factor", "dislikes_generic", "max_words",
                                          "prefers_questions", "responsiveness", "is_scammer"], "client hidden")
    need(accts, ["account_id", "name", "title", "hourly_rate", "skills", "success_score", "token", "connects_balance",
                 "weekly_allowance"], "accounts")
    ids = [j["job_id"] for j in jobs]
    if len(ids) != len(set(ids)):
        ERR.append("seed: duplicate job ids")
    cids = {c["client_id"] for c in clients}
    if any(j["client_id"] not in cids for j in jobs):
        ERR.append("seed: job with unknown client")
    if any(j["duplicate_of"] and j["duplicate_of"] not in set(ids) for j in jobs):
        ERR.append("seed: dangling duplicate_of")
    comp = json.loads((d / "competitors.json").read_text())
    if len(comp["quality_quantiles"]) != 21:
        ERR.append("competitors: need 21 quantiles")
    ms = json.loads((d / "market_stats.json").read_text())
    if "_all" not in ms:
        ERR.append("market_stats: no _all")
    bad = sum(j["is_scam"] or j["has_injection"] for j in jobs)
    count("gigsim_seed/jobs.jsonl", len(jobs), f"scam={sum(j['is_scam'] for j in jobs)} inj={sum(j['has_injection'] for j in jobs)} "
          f"({bad/len(jobs):.1%}) reposts={sum(1 for j in jobs if j['duplicate_of'])} open_at_start={sum(j['release_minute'] <= 0 for j in jobs)}")
    per_client = Counter(j['client_id'] for j in jobs)
    count("gigsim_seed/clients.jsonl", len(clients), f"clients with >1 seed job={sum(1 for v in per_client.values() if v > 1)} "
          f"scammers={sum(c['hidden']['is_scammer'] for c in clients)}")
    count("gigsim_seed/accounts.jsonl", len(accts))
    return set(ids)


def gitignore():
    files = [str(p.relative_to(ROOT)).replace("\\", "/") for sub in ("data/raw", "data/processed", "data/cache")
             for p in (ROOT / sub).rglob("*") if p.is_file()]
    if not files:
        return
    # minimal .gitignore matcher (no git invocation): dir patterns, path globs and basename globs, with negation
    pats = [ln.strip() for ln in (ROOT / ".gitignore").read_text().splitlines() if ln.strip() and not ln.startswith("#")]

    def ignored(path: str) -> bool:
        parts = path.split("/")
        res = False
        for pat in pats:
            neg = pat.startswith("!")
            p = pat[1:] if neg else pat
            hit = False
            if p.endswith("/"):
                d = p.rstrip("/")
                prefixes = ["/".join(parts[:i]) for i in range(1, len(parts))]
                hit = any(fnmatch.fnmatch(x, d) or fnmatch.fnmatch(x.split("/")[-1], d) if "/" not in d else fnmatch.fnmatch(x, d)
                          for x in prefixes)
            elif "/" in p:
                hit = fnmatch.fnmatch(path, p.lstrip("/"))
            else:
                hit = any(fnmatch.fnmatch(x, p) for x in parts)
            if hit:
                res = not neg
        return res

    leaks = [f for f in files if not ignored(f)]
    if leaks:
        ERR.append(f"{len(leaks)} data files not gitignored, e.g. {leaks[:3]}")
    count("gitignore check (raw+processed+cache files)", len(files), f"not ignored={len(leaks)}")


def main():
    ev = personas()
    sid = seed()
    evalsets(ev, sid)
    gitignore()
    w = max(len(c[0]) for c in COUNTS)
    print(f"\n{'file':{w}s}  {'rows':>6s}  notes")
    for name, n, note in COUNTS:
        print(f"{name:{w}s}  {n:6d}  {note}")
    if ERR:
        print(f"\n{len(ERR)} problem(s):")
        for e in ERR:
            print("  -", e)
        sys.exit(1)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
