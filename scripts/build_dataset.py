"""K1-K6 -> data/processed/*, data/taxonomy.yaml (read), evals/datasets/*, data/processed/gigsim_seed/*.

Usage: python scripts/build_dataset.py [--no-label] [--label-limit N] [--relabel-only]
Labeller: GIGBID_LABEL_BACKEND=qwen|claude|cache (default qwen), GIGBID_LABEL_DEADLINE_MIN=N.
Requires data/raw/k1..k6 (scripts/download_kaggle.py) and data/personas/* (scripts/build_personas.py).
Gold labelling calls are cached under data/cache/llm/.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.ingest.dataset import build  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-label", action="store_true", help="skip the LLM gold labelling (gold is rule-only)")
    ap.add_argument("--label-limit", type=int, default=None, help="label only the first N jobs per persona")
    ap.add_argument("--relabel-only", action="store_true",
                    help="only (re)label gold for the existing dev/held-out files; seed and splits untouched")
    a = ap.parse_args()
    if a.relabel_only:
        from rag.ingest.gold import relabel_existing

        print(relabel_existing(label_limit=a.label_limit))
    else:
        build(label=not a.no_label, label_limit=a.label_limit)
