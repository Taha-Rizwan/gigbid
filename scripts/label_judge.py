"""Blind human labelling for judge calibration. Shows one proposal at a time (with its job post) and asks
for an overall score 1-5 using the same rubric as the LLM judge. Saves after every answer, so you can stop
and resume. The judge's own score is never shown.

    .venv/Scripts/python scripts/label_judge.py
Then:  .venv/Scripts/python -m evals.runners.judge_calibration
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "evals" / "datasets" / "human_labels.jsonl"
RUBRIC = """Score the proposal as the CLIENT who posted the job (1-5):
  relevance (addresses this job), evidence (concrete past work), personalisation (not a template),
  clarity (concise, structured), professionalism (no buzzwords or policy problems, clear next step).
  1 = would ignore   2 = weak   3 = okay   4 = good, would probably reply   5 = would definitely reply"""


def job_posts() -> dict[str, dict]:
    out = {}
    for p in (ROOT / "evals" / "datasets").glob("dev_*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["job_id"]] = r
    return out


def main() -> None:
    if not LABELS.exists():
        print("No labelling file yet. Run:  .venv/Scripts/python -m evals.runners.judge_calibration\n"
              "(it creates evals/datasets/human_labels.jsonl from the proposal eval samples).")
        return
    rows = [json.loads(x) for x in LABELS.read_text(encoding="utf-8").splitlines() if x.strip()]
    jobs = job_posts()
    todo = [i for i, r in enumerate(rows) if r.get("human_overall") is None]
    print(f"{len(rows) - len(todo)} of {len(rows)} already labelled.\n\n{RUBRIC}\n")
    name = input("Your name (stored as labeler): ").strip() or "student"
    for n, i in enumerate(todo, 1):
        r = rows[i]
        job = jobs.get(r["job_id"], {})
        print("\n" + "=" * 90)
        print(f"[{n}/{len(todo)}]  JOB: {job.get('title', r['job_id'])}")
        print(textwrap.fill((job.get("description") or "")[:900], 90))
        print("-" * 90 + f"\nPROPOSAL (bid {r.get('bid_amount')} {r.get('rate_type')}):\n")
        print(textwrap.fill(r["cover_letter"], 90, replace_whitespace=False))
        for a in r.get("screening_answers") or []:
            print("\nANSWER: " + textwrap.fill(a, 90))
        while True:
            s = input("\nScore 1-5 (s = skip, q = quit): ").strip().lower()
            if s in {"1", "2", "3", "4", "5"}:
                r["human_overall"], r["labeler"] = int(s), name
                break
            if s in {"s", "q"}:
                break
        if s == "q":
            break
        LABELS.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    LABELS.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    done = sum(r.get("human_overall") is not None for r in rows)
    print(f"\nSaved. {done} of {len(rows)} labelled. Now run:  .venv/Scripts/python -m evals.runners.judge_calibration")


if __name__ == "__main__":
    main()
