"""Builds data/deploy_seed/ (committed): a compact GigSim seed for the deployed demo and CI.

Takes the full generated seed (data/processed/gigsim_seed, gitignored) and keeps N jobs per release
window plus every scam / injection / duplicate job and the clients they reference. Falls back to the
built-in GigSim fixtures if the full seed has not been generated. Job text is derived from the
K1 Kaggle dataset (ODC-By); see docs/DATA_CARD.md for attribution.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT / "data" / "processed" / "gigsim_seed"
OUT = ROOT / "data" / "deploy_seed"


def jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--open-jobs", type=int, default=600, help="jobs already open at start")
    ap.add_argument("--stream-jobs", type=int, default=900, help="jobs released over time (live stream)")
    ap.add_argument("--special-jobs", type=int, default=150, help="scam / injection / duplicate jobs")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not (FULL / "jobs.jsonl").exists():
        for f in (ROOT / "gigsim" / "fixtures").iterdir():
            shutil.copy(f, OUT / f.name)
        print("full seed missing; copied GigSim fixtures")
        return
    rng = random.Random(a.seed)
    jobs = jsonl(FULL / "jobs.jsonl")
    special = [j for j in jobs if j.get("is_scam") or j.get("has_injection") or j.get("duplicate_of")]
    open_ = [j for j in jobs if (j.get("release_minute") or 0) <= 0 and j not in special]
    stream = [j for j in jobs if (j.get("release_minute") or 0) > 0 and j not in special]
    special = rng.sample(special, min(a.special_jobs, len(special)))
    keep = special + rng.sample(open_, min(a.open_jobs, len(open_))) + rng.sample(stream, min(a.stream_jobs, len(stream)))
    ids = {j["job_id"] for j in keep}
    keep = [j for j in keep if not j.get("duplicate_of") or j["duplicate_of"] in ids]
    client_ids = {j["client_id"] for j in keep}
    clients = [c for c in jsonl(FULL / "clients.jsonl") if c["client_id"] in client_ids]
    (OUT / "jobs.jsonl").write_text("\n".join(json.dumps(j) for j in keep) + "\n", encoding="utf-8")
    (OUT / "clients.jsonl").write_text("\n".join(json.dumps(c) for c in clients) + "\n", encoding="utf-8")
    for name in ("accounts.jsonl", "market_stats.json", "competitors.json"):
        if (FULL / name).exists():
            shutil.copy(FULL / name, OUT / name)
    print(f"deploy seed: {len(keep)} jobs ({len(special)} scam/injection/duplicate), {len(clients)} clients")


if __name__ == "__main__":
    main()
