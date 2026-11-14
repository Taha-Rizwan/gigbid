"""Write ~150 past proposals per persona for K1 jobs outside the eval sets and label their outcomes
with GigSim's stateless scorer (POST /admin/score).

Starts GigSim on :8081 with data/processed/gigsim_seed (and a separate DB) unless one is already
running at GIGSIM_ADMIN_URL. Usage: python scripts/label_proposals.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.ingest.proposals import build  # noqa: E402

if __name__ == "__main__":
    build()
