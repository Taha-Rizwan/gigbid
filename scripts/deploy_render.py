"""Create (or update) the GigBid web service on Render from the public GitHub repo.

    python scripts/deploy_render.py [--plan free]

Uses infra/render/Dockerfile (single container). Runtime secrets are copied from .env into the
service's environment; values are never printed.
"""

from __future__ import annotations

import argparse
import sys

import httpx
from dotenv import dotenv_values

API = "https://api.render.com/v1"
NAME = "gigbid"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="free")
    a = ap.parse_args()
    env = dotenv_values(".env")
    h = {"Authorization": f"Bearer {env['RENDER_API_KEY']}", "Accept": "application/json", "Content-Type": "application/json"}
    c = httpx.Client(base_url=API, headers=h, timeout=60)
    owner = c.get("/owners", params={"limit": 1}).json()[0]["owner"]["id"]
    url = f"https://{NAME}.onrender.com"
    keys = ["DATABASE_URL", "GROQ_API_KEY", "ANTHROPIC_API_KEY", "LANGSMITH_API_KEY", "APP_SECRET_KEY",
            "TOKEN_ENCRYPTION_KEY", "MCP_AUTH_TOKEN", "REVIEWER_PASSWORD", "GIGSIM_ADMIN_TOKEN"]
    env_vars = [{"key": k, "value": env[k]} for k in keys if env.get(k)]
    env_vars += [{"key": k, "value": v} for k, v in {
        "MODEL_PROFILE": "paid", "LANGSMITH_PROJECT": "gigbid", "LANGSMITH_TRACING": "true", "PORT": "10000"}.items()]
    existing = [s["service"] for s in c.get("/services", params={"name": NAME, "limit": 5}).json()]
    if existing:
        sid = existing[0]["id"]
        url = existing[0]["serviceDetails"].get("url") or url
    else:
        body = {
            "type": "web_service", "name": NAME, "ownerId": owner,
            "repo": "https://github.com/Taha-Rizwan/gigbid", "branch": "main", "autoDeploy": "yes",
            "serviceDetails": {
                "runtime": "docker", "plan": a.plan, "region": "oregon", "healthCheckPath": "/login",
                "envSpecificDetails": {"dockerfilePath": "./infra/render/Dockerfile", "dockerContext": "."},
            },
            "envVars": env_vars,
        }
        r = c.post("/services", json=body)
        if r.status_code >= 300:
            sys.exit(f"create failed: {r.status_code} {r.text[:500]}")
        svc = r.json()["service"]
        sid, url = svc["id"], svc["serviceDetails"].get("url") or url
    c.put(f"/services/{sid}/env-vars", json=env_vars + [
        {"key": "PUBLIC_BASE_URL", "value": url}, {"key": "CORS_ORIGINS", "value": f'["{url}"]'}]).raise_for_status()
    c.post(f"/services/{sid}/deploys", json={"clearCache": "do_not_clear"})
    print(f"service {sid}\nurl {url}\ndashboard https://dashboard.render.com/web/{sid}")


if __name__ == "__main__":
    main()
