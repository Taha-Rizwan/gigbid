"""Repository rules CI enforces (exit 1 on any violation):

1. No secrets in tracked files.
2. Nothing under gigsim/ changed since the frozen tag `gigsim-v1.0` (once that tag exists).
3. Every prompt lives in agent/prompts/: no inline system prompts in node or graph code.
4. Every number in the README results sections traces to a file in evals/results/.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(
    r"(gsk_[A-Za-z0-9]{30,}|lsv2_[a-z]{2}_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{30,}|KGAT_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}"
    r"|github_pat_[A-Za-z0-9_]{40,}|sk-ant-[A-Za-z0-9_-]{30,}|npg_[A-Za-z0-9]{10,}|postgres(?:ql)?://[^:\s]+:[^@\s]{8,}@[^\s]*neon"
    r"|rediss://[^:\s]*:[^@\s]{12,}@)"
)
INLINE_PROMPT = re.compile(r"""(SystemMessage\(\s*["'](You are|You're)|["']You are (the|a|an) [A-Z])""")


def tracked() -> list[str]:
    return subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()


def check_secrets(files: list[str]) -> list[str]:
    bad = []
    for f in files:
        p = ROOT / f
        if p.suffix in {".png", ".jpg", ".pdf", ".ico", ".woff", ".woff2", ".sqlite", ".lock"} or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if SECRET.search(text):
            bad.append(f"possible secret in {f}")
    if ".env" in files:
        bad.append(".env is tracked")
    return bad


def check_gigsim_frozen() -> list[str]:
    tags = subprocess.run(["git", "tag", "-l", "gigsim-v1.0"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if not tags:
        return []
    diff = subprocess.run(["git", "diff", "--name-only", "gigsim-v1.0", "HEAD", "--", "gigsim/"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    return [f"gigsim/ changed since gigsim-v1.0: {diff.replace(chr(10), ', ')}"] if diff else []


def check_prompts(files: list[str]) -> list[str]:
    bad = []
    for f in files:
        if f.endswith(".py") and f.startswith(("agent/nodes/", "agent/graphs/", "rag/", "apps/api/")):
            if INLINE_PROMPT.search((ROOT / f).read_text(encoding="utf-8")):
                bad.append(f"inline system prompt in {f} (move it to agent/prompts/)")
    return bad


def check_numbers() -> list[str]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"<!-- results:start -->(.*?)<!-- results:end -->", readme, re.S)
    if not m:
        return []
    corpus = " ".join(p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "evals" / "results").glob("*")
                      if p.suffix in {".json", ".csv", ".md"})
    bad = []
    for num in set(re.findall(r"(?<![\w.])\d+\.\d+(?![\w.])", m.group(1))):
        if num not in corpus:
            bad.append(f"README number {num} not found in evals/results/")
    return bad


def main() -> int:
    files = tracked()
    problems = check_secrets(files) + check_gigsim_frozen() + check_prompts(files) + check_numbers()
    for p in problems:
        print("FAIL:", p)
    print("ci guards:", "ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
