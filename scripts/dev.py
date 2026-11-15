"""Local dev stack without Docker: GigSim, the three MCP servers, the API (inline worker), and
optionally the web app. Logs go to data/cache/logs/. Ctrl+C stops everything.

    python scripts/dev.py            # backend only
    python scripts/dev.py --web      # also `npm run dev` in apps/web
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable  # the interpreter that launched this script (any venv)
LOGS = ROOT / "data" / "cache" / "logs"

SERVICES = [
    ("gigsim", [PY, "-m", "uvicorn", "gigsim.app:app", "--port", "8081", "--log-level", "warning"], {}),
    ("mcp_marketplace", [PY, "-m", "mcp_servers.marketplace.server"], {}),
    ("mcp_portfolio", [PY, "-m", "mcp_servers.portfolio.server"], {}),
    ("mcp_workspace", [PY, "-m", "mcp_servers.workspace.server"], {}),
    ("api", [PY, "-m", "apps.api"], {"WORKER_MODE": os.environ.get("WORKER_MODE", "inline")}),
]


def main() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    env = os.environ | {"HF_HUB_DISABLE_SYMLINKS_WARNING": "1", "PYTHONUNBUFFERED": "1"}
    services = list(SERVICES)
    if "--web" in sys.argv:
        services.append(("web", ["npm.cmd" if os.name == "nt" else "npm", "run", "dev"], {"_cwd": "apps/web"}))
    procs = []
    for name, cmd, extra in services:
        cwd = ROOT / extra.pop("_cwd", ".")
        log = open(LOGS / f"{name}.log", "w", encoding="utf-8")
        procs.append((name, subprocess.Popen(cmd, cwd=cwd, env=env | extra, stdout=log, stderr=subprocess.STDOUT)))
        print(f"started {name:16} -> {LOGS / (name + '.log')}")
    try:
        while True:
            time.sleep(2)
            for name, p in procs:
                if p.poll() is not None:
                    print(f"{name} exited with {p.returncode}; see its log")
                    procs.remove((name, p))
    except KeyboardInterrupt:
        pass
    finally:
        for _, p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
