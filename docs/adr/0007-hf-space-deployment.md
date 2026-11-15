# ADR 0007: Deploy to one Hugging Face Docker Space, with Neon Postgres and Upstash Redis

- Status: accepted (replaces D28, the single-VM plan)
- Plan reference: D28b and Q3 in `PLAN.md` §0

## Context

There is no VM and no local Docker, and only about 18 GB of free disk. The brief needs a public
URL that stays live until grades are out, a reviewer login, and `docker compose up` working
locally (R10). Everything must be free with no card.

## Decision

- **One Hugging Face Docker Space** (`infra/hf/Dockerfile`) runs GigSim, the three MCP servers,
  the API, the Arq worker and the Next.js server under `supervisord`
  (`infra/hf/supervisord.conf`). Only the web server listens publicly, on port 7860. The API
  (:8000), MCP servers (:8101–8103) and GigSim (:8081) bind to 127.0.0.1.
- **Neon** for Postgres + pgvector and **Upstash** for Redis, configured as Space secrets
  (`DATABASE_URL`, `REDIS_URL`).
- The image bakes in the fastembed embedding and reranker models, so startup downloads nothing.
- GigSim seeds from the committed `data/deploy_seed/` (built by `scripts/make_deploy_seed.py`)
  into `/tmp/gigsim.sqlite`, with `GIGSIM_CLOCK_SPEED=10`.
- `infra/docker-compose.yml` stays the local and CI path. The `compose` job in
  `.github/workflows/ci.yml` builds it, waits for health and checks `/api/health` returns `ok`.
- The plan put the web app on Vercel. The implementation serves it from the same Space, so the
  API stays same-origin (ADR 0003) and there is one deployment, not two.

## Alternatives rejected

- **Single VM with Caddy (D28).** No VM available.
- **Render free tier.** 512 MB RAM is too small for the embedding models, and it sleeps.
- **Vercel + Render + Neon + Upstash.** Four dashboards and cross-origin cookies.

## Consequences

- The Space builds on Hugging Face's servers, so no local Docker is needed.
- Free Spaces sleep after a period without visits and take about a minute to wake. Nothing in
  `.github/workflows/` pings the Space at the time of writing (see `docs/RUNBOOK.md`).
- GigSim's state is in `/tmp` and resets on every Space restart, while Postgres (Neon) keeps the
  app's jobs and proposals. After a restart the pipeline board can reference GigSim proposals that
  no longer exist.
- GigSim's `/admin` endpoints are not reachable from the internet, which matters for hidden-test
  injection (RUNBOOK).
- One container means one failure domain. supervisord restarts crashed processes
  (`autorestart=true`), which also means the "kill the marketplace server" drill only lasts until
  supervisord restarts it.
