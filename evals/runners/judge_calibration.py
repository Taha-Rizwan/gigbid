"""Judge calibration: Cohen's kappa (exact and quadratic-weighted) between the LLM judge's overall
score and human labels.

Human labels live in evals/datasets/human_labels.jsonl. If it does not exist, a template is created
from 30 proposals in evals/results/proposals_samples.jsonl (blind: the judge score is not copied
into it) with an empty `human_overall` (1-5) for the human to fill. Until labels are filled in, the
result has "status": "awaiting_human_labels".

    python -m evals.runners.judge_calibration [--n 30]
Output: evals/results/judge_calibration.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from evals.runners.common import DATASETS_DIR, RESULTS_DIR, header, load_jsonl, setup, write_json


def main(args) -> None:
    setup(None)
    from evals.metrics import accuracy, cohen_kappa

    labels_path = Path(args.labels)
    samples = load_jsonl(Path(args.out_dir) / "proposals_samples.jsonl") or load_jsonl(RESULTS_DIR / "proposals_samples.jsonl")
    created = False
    if not labels_path.exists() and samples:
        pick = sorted(samples, key=lambda s: (s["job_id"], s.get("variant") or ""))
        random.Random(11).shuffle(pick)
        pick = pick[: args.n]
        labels_path.parent.mkdir(parents=True, exist_ok=True)
        labels_path.write_text("".join(json.dumps({
            "sample_id": f"{s['job_id']}|{s.get('variant')}|{s.get('profile')}", "job_id": s["job_id"],
            "persona": s["persona"], "variant": s.get("variant"), "profile": s.get("profile"),
            "cover_letter": s["final_cover_letter"], "screening_answers": s.get("final_screening_answers") or [],
            "bid_amount": s.get("bid_amount"), "rate_type": s.get("rate_type"),
            "human_overall": None, "labeler": None, "notes": ""}, ensure_ascii=False) + "\n" for s in pick),
            encoding="utf-8")
        created = True
        print(f"wrote template {labels_path} ({len(pick)} proposals); fill human_overall 1-5")
    labels = load_jsonl(labels_path)
    judge = {f"{s['job_id']}|{s.get('variant')}|{s.get('profile')}": s.get("judge_overall") for s in samples}
    pairs = [(int(lab["human_overall"]), int(judge[lab["sample_id"]])) for lab in labels
             if lab.get("human_overall") not in (None, "") and judge.get(lab["sample_id"]) is not None]
    base = header("judge_calibration", args, len(pairs)) | {
        "labels_file": str(labels_path.relative_to(labels_path.parents[2])) if labels_path.is_absolute() else str(labels_path),
        "template_created_now": created, "n_label_rows": len(labels)}
    if len(pairs) < 5:
        write_json(f"judge_calibration{args.tag}.json", base | {
            "status": "awaiting_human_labels",
            "reason": f"{len(pairs)} proposals have both a human_overall and a judge score (need >= 5)"}, args.out_dir)
        return
    h, j = [p[0] for p in pairs], [p[1] for p in pairs]
    write_json(f"judge_calibration{args.tag}.json", base | {
        "status": "complete" if len(pairs) == len(labels) else "partial",
        "kappa_exact": cohen_kappa(h, j, labels=[1, 2, 3, 4, 5]),
        "kappa_quadratic": cohen_kappa(h, j, labels=[1, 2, 3, 4, 5], weights="quadratic"),
        "exact_agreement": accuracy(h, j),
        "within_one": sum(abs(a - b) <= 1 for a, b in pairs) / len(pairs),
        "human_mean": sum(h) / len(h), "judge_mean": sum(j) / len(j)}, args.out_dir)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", default=str(DATASETS_DIR / "human_labels.jsonl"))
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--out-dir", default=str(RESULTS_DIR))
    ap.add_argument("--tag", default="")
    main(ap.parse_args())
