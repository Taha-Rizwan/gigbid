"""Exit non-zero when the smoke eval crosses a threshold in evals/thresholds.yaml.

    python -m evals.runners.check_thresholds [--file evals/results/smoke.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def check(smoke: dict, limits: dict) -> list[str]:
    fails = []
    u = smoke.get("unsupported_claims_per_proposal")
    if "max_unsupported_claims_per_proposal" in limits:
        if u is None:
            fails.append("unsupported_claims_per_proposal missing")
        elif u > limits["max_unsupported_claims_per_proposal"]:
            fails.append(f"unsupported claims/proposal {u:.3f} > {limits['max_unsupported_claims_per_proposal']}")
    f1 = smoke.get("bid_skip_f1")
    if "min_bid_skip_f1" in limits:
        if f1 is None:
            fails.append("bid_skip_f1 missing")
        elif f1 < limits["min_bid_skip_f1"]:
            fails.append(f"bid/skip F1 {f1:.3f} < {limits['min_bid_skip_f1']}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(ROOT / "evals" / "results" / "smoke.json"))
    ap.add_argument("--thresholds", default=str(ROOT / "evals" / "thresholds.yaml"))
    a = ap.parse_args()
    p = Path(a.file)
    if not p.exists():
        print(f"FAIL: {p} not found")
        return 2
    fails = check(json.loads(p.read_text(encoding="utf-8")), yaml.safe_load(Path(a.thresholds).read_text())["smoke"])
    for f in fails:
        print("FAIL:", f)
    if not fails:
        print("thresholds OK")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
