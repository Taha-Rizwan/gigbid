"""Collects the smoke-run results (rag_eval / decision_eval / proposal_eval run with --tag _smoke on a
30-job sample) into evals/results/smoke.json, which check_thresholds.py gates CI on.

    make eval-smoke     (runs the three runners, then this)
"""

from __future__ import annotations

import json

from evals.runners.common import RESULTS_DIR, git_sha


def main() -> None:
    import datetime as dt

    def load(n):
        p = RESULTS_DIR / n
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    rv, dec, prop = load("rag_variants_smoke.json"), load("decisions_smoke.json"), load("proposals_smoke.json")
    out = {"generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "git_sha_or_null": git_sha(),
           "config_snapshot": (dec or rv or {}).get("config_snapshot"),
           "n": (dec or {}).get("n"), "sources": ["rag_variants_smoke.json", "decisions_smoke.json", "proposals_smoke.json"],
           "status": "complete" if all(x and x.get("status") == "complete" for x in (rv, dec, prop)) else "partial"}
    if rv:
        out["retrieval"] = {v: {"n": b["overall"].get("n"), "recall@5": b["overall"].get("recall@5"),
                                "ndcg@10": b["overall"].get("ndcg@10")} for v, b in rv["variants"].items()}
    if dec:
        out["bid_skip_f1"] = dec["dev"].get("bid_skip", {}).get("f1")
        out["bid_skip_n"] = dec["dev"].get("n")
        out["scam_recall"] = dec["dev"].get("scam", {}).get("recall")
    if prop:
        res = next(iter(prop["results"].values()), {}) if prop.get("results") else {}
        out["unsupported_claims_per_proposal"] = res.get("unsupported_after_mean")
        out["proposals_n"] = res.get("n_proposals")
    p = RESULTS_DIR / "smoke.json"
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {p}")


if __name__ == "__main__":
    main()
