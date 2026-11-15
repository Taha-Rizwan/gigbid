"""One command to put GigBid online from this laptop (used because free Hugging Face Docker Spaces
were withdrawn). Starts the Cloudflare tunnel, reads its public URL, then starts GigSim, the three
MCP servers, the API and the production web app with PUBLIC_BASE_URL set to that URL.

    .venv/Scripts/python scripts/go_live.py

Prints the public URL and saves it to data/cache/live_url.txt. Ctrl+C stops everything.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "data" / "cache" / "logs"
CLOUDFLARED = Path(os.environ.get("CLOUDFLARED", Path.home() / "tools" / "cloudflared.exe"))
PY = str(ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python"))


def main() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    tunnel_log = LOGS / "tunnel.log"
    procs = [subprocess.Popen([str(CLOUDFLARED), "tunnel", "--no-autoupdate", "--url", "http://localhost:3000"],
                              stdout=open(tunnel_log, "w"), stderr=subprocess.STDOUT)]
    url = None
    for _ in range(60):
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", tunnel_log.read_text(errors="ignore"))
        if m:
            url = m.group(0)
            break
        time.sleep(1)
    if not url:
        sys.exit("tunnel did not report a URL; see data/cache/logs/tunnel.log")
    (ROOT / "data" / "cache" / "live_url.txt").write_text(url)
    env = os.environ | {
        "GIGSIM_SEED_DIR": "data/deploy_seed", "GIGSIM_DB": "data/cache/gigsim_live.sqlite",
        "GIGSIM_CLOCK_SPEED": "10", "GIGSIM_LLM_DISABLED": "1", "GIGSIM_ERROR_RATE": "0.02",
        "PUBLIC_BASE_URL": url, "APP_ENV": "production", "WORKER_MODE": "inline",
    }
    procs.append(subprocess.Popen([PY, "scripts/dev.py"], cwd=ROOT, env=env))
    procs.append(subprocess.Popen(["npm.cmd" if os.name == "nt" else "npm", "run", "start:standalone"],
                                  cwd=ROOT / "apps" / "web", env=os.environ | {"PORT": "3000", "HOSTNAME": "127.0.0.1"},
                                  stdout=open(LOGS / "web.log", "w"), stderr=subprocess.STDOUT))
    print(f"\nGigBid is live at {url}\n(reviewer password: REVIEWER_PASSWORD in .env). Ctrl+C to stop.\n")
    try:
        while all(p.poll() is None for p in procs):
            time.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
