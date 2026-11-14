"""Generate data/personas/{ai_ml,fullstack,data_analyst} from scripts/persona_specs.yaml.

Usage: python scripts/build_personas.py [persona_id ...]
All LLM calls are cached under data/cache/llm/, so reruns are free and resume after failures.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.ingest.personas import build  # noqa: E402

if __name__ == "__main__":
    build([a for a in sys.argv[1:] if not a.startswith("-")] or None)
