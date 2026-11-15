# Runbook

How to run, configure, seed, deploy and drill GigBid. Commands assume the repo root. On Windows,
use `.venv/Scripts/python` where this file says `python`.

## 1. Run locally without Docker

Needs Python 3.12, [uv](https://docs.astral.sh/uv/), Node 22, and a Postgres database (Neon free
tier works; local Postgres with the `vector` extension also works).

```bash
uv sync --extra dev                       # creates .venv from uv.lock
cp .env.example .env                      # then fill in the values from §3
cd apps/web && npm ci && cd ../..
python scripts/dev.py --web               # GigSim :8081, MCP :8101-8103, API :8000, web :3000
```

`scripts/dev.py` starts GigSim, the three MCP servers and the API, plus `npm run dev` with
`--web`. Logs go to `data/cache/logs/<service>.log`. It sets `WORKER_MODE=inline`, so agent runs
execute as asyncio tasks inside the API process (`apps/api/jobs_queue.py`). **Inline mode runs no
cron jobs**: no scheduled scouting, no event sync and no `retry_queued`. For those, and for the
drills in §7 and §8, run the real worker as well:

```bash
# .env: REDIS_URL=rediss://...upstash...   and WORKER_MODE=arq
python scripts/dev.py --web
arq worker.main.WorkerSettings            # second terminal
```

`DATABASE_URL` must be a plain `postgresql://user:pass@host/db` URL (psycopg conninfo). The
`postgresql+psycopg://` form in the starter `.env.example` is an SQLAlchemy URL and does not work.
When `DATABASE_URL` is set, the API uses the durable Postgres checkpointer and store
(`agent/memory/store.py`). Without it, there is no app database at all (`common/db.py` raises).

One-off CLI run of the bid graph on a GigSim job (in-memory MCP, no API needed):

```bash
python -m agent.runner job_001 --persona ai_ml            # stops at the approval interrupt
python -m agent.runner job_001 --persona ai_ml --approve  # dev only: auto-approves and submits to GigSim
```

`job_001` exists in the built-in fixtures (`gigsim/fixtures/jobs.jsonl`), which GigSim uses when
`data/processed/gigsim_seed` has not been built. With another seed, take a job id from
`curl localhost:8081/v1/jobs -H "Authorization: Bearer gigsim-token-ai"`.

## 2. Run with Docker

```bash
docker compose -f infra/docker-compose.yml up --build
# web http://localhost:3000, API http://localhost:8000, GigSim http://localhost:8081
docker compose -f infra/docker-compose.yml --profile local-models up --build   # also starts Ollama
```

Compose starts Postgres (`pgvector/pgvector:pg16`), Redis, GigSim (`GIGSIM_CLOCK_SPEED=10`), the
three MCP servers, the API, the Arq worker and the web app. Secrets come from the repo-root `.env`.
Ollama only starts with the `local-models` profile. It is used by `MODEL_PROFILE=open_local`, and
the models (`qwen3:4b`, `qwen3:8b`) must be pulled into it first, with
`docker compose exec ollama ollama pull qwen3:8b`. The `compose` job in `.github/workflows/ci.yml`
brings the stack up on every push and checks that `/api/health` reports `ok`.

## 3. Environment variables

Secrets come only from the environment. `.env` is git-ignored, and `scripts/ci_guards.py` fails
CI if `.env` is tracked or a token pattern appears in a tracked file. Settings classes:
`apps/api/settings.py` (API), `agent/settings.py` (config overrides), `gigsim/config.py`
(GigSim).

### App, API and worker

| Variable | Default | Read in | Purpose |
|---|---|---|---|
| `DATABASE_URL` | none (required) | `common/db.py`, `agent/memory/store.py`, MCP servers | Postgres for app tables, checkpointer, store, audit log, idempotency |
| `REDIS_URL` | none | `apps/api/jobs_queue.py`, `worker/main.py` | Arq queue. Unset means inline mode. `rediss://` turns on TLS (Upstash). |
| `WORKER_MODE` | `arq` (`inline` in `scripts/dev.py`) | `apps/api/jobs_queue.py` | `inline` runs tasks inside the API |
| `APP_ENV` | `development` | `apps/api/settings.py` | `production` makes the session cookie `Secure` |
| `APP_SECRET_KEY` | `dev-only-change-me` | `apps/api/service.py`, `common/security.py` | Signs session JWTs. Also derives the Fernet key when `TOKEN_ENCRYPTION_KEY` is unset. |
| `TOKEN_ENCRYPTION_KEY` | derived | `common/security.py` | Fernet key for stored OAuth tokens. Set it in production. |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | `apps/api/main.py` | JSON list. Only needed if the browser calls the API cross-origin. |
| `PUBLIC_BASE_URL` | `http://localhost:3000` | `apps/api/service.py` | Public origin, used for OAuth redirects and the Upwork client ID metadata document |
| `REVIEWER_EMAIL` | `reviewer@gigbid.dev` | `apps/api/settings.py` | Reviewer login email |
| `REVIEWER_PASSWORD` | none | `apps/api/service.py` `seed_reviewer()` | Creates the reviewer account on startup. Never committed. |
| `API_HOST`, `API_PORT` | `127.0.0.1`, `8000` | `apps/api/__main__.py` | `python -m apps.api` |
| `GIGBID_CONFIG` | `agent/config.yaml` | `agent/settings.py` | Use another config file |
| `MARKETPLACE_MODE` | from config | `agent/settings.py` | Overrides `marketplace.mode` (`gigsim` or `upwork_live`) |
| `MODEL_PROFILE` | from config (`open`) | `agent/settings.py` | Overrides `models.profile` |
| `GIGBID_INPROCESS_MCP` | unset | `apps/api/runs.py` | `1` uses in-memory MCP sessions instead of HTTP (tests) |

### MCP

| Variable | Default | Purpose |
|---|---|---|
| `MCP_AUTH_TOKEN` | `dev-mcp-token` | Shared bearer token between clients (`agent/mcp_client.py`) and servers (`common/mcp_http.py`). Change it everywhere outside local dev. |
| `MCP_MARKETPLACE_URL`, `MCP_PORTFOLIO_URL`, `MCP_WORKSPACE_URL` | `http://127.0.0.1:8101/mcp`, `:8102/mcp`, `:8103/mcp` | Where the agents and `/api/health` find the servers |
| `MCP_HOST` | `127.0.0.1` | Bind address of the MCP servers |
| `MCP_MARKETPLACE_PORT`, `MCP_PORTFOLIO_PORT`, `MCP_WORKSPACE_PORT` | `8101`, `8102`, `8103` | Ports |
| `GIGSIM_BASE_URL` | `http://localhost:8081` | GigSim REST base for the adapter and health check |
| `GIGSIM_DEFAULT_TOKEN` | `gigsim-token-ai` | GigSim account token for users without a profile. Profiles store their own (`PERSONA_TOKEN` in `apps/api/service.py`). |
| `PORTFOLIO_PERSONA`, `GIGBID_PERSONAS_DIR` | `ai_ml`, `data/personas` | Portfolio server: default persona and corpus folder (point it at your own portfolio) |

### Models and tracing

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Open profile models, Prompt Guard, GigSim's client LLM |
| `ANTHROPIC_API_KEY` | `paid` profile and the eval judge (`claude-haiku-5-5`) |
| `CEREBRAS_API_KEY`, `OPENAI_API_KEY` | Only if a profile in `agent/config.yaml` names provider `cerebras` / `openai` (none does by default) |
| `OLLAMA_BASE_URL` | `open_local` profile (compose sets `http://ollama:11434/v1`) |
| `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT` | LangSmith tracing (compose defaults: tracing `true`, project `gigbid`) |

### Live mode (Upwork) and GitHub

| Variable | Purpose |
|---|---|
| `UPWORK_CLIENT_ID`, `UPWORK_CLIENT_SECRET` | Optional pre-registered OAuth client. Without them, GigBid uses its client ID metadata document at `{PUBLIC_BASE_URL}/api/oauth/upwork/client-metadata.json`. |
| `UPWORK_MCP_URL` | Declared in `apps/api/settings.py`, but the adapter uses the constant `UPWORK_MCP` in `upwork_live.py` |
| `GITHUB_TOKEN`, `GITHUB_REPO_URL` | For GitHub MCP repo ingestion. Declared in settings, but no code reads them yet. |

### GigSim (`gigsim/config.py`)

| Variable | Default | Purpose |
|---|---|---|
| `GIGSIM_DB` | `data/cache/gigsim.sqlite` | SQLite file (the Space uses `/tmp/gigsim.sqlite`) |
| `GIGSIM_SEED_DIR` | `data/processed/gigsim_seed` | Seed folder. Falls back to `gigsim/fixtures/`. The Space uses `data/deploy_seed`. |
| `GIGSIM_ADMIN_TOKEN` | `gigsim-admin` | `X-Admin-Token` for `/admin/*`. **Change it in any shared deployment.** |
| `GIGSIM_RATE_PER_MIN` | `60` | Token bucket per account |
| `GIGSIM_ERROR_RATE` | `0.02` | Seeded 503 chaos on `/v1` |
| `GIGSIM_START`, `GIGSIM_CLOCK_SPEED`, `GIGSIM_SEED` | `2024-02-20T09:00:00Z`, `0`, `42` | Simulated clock and seed. Speed is sim minutes per real minute; 0 means manual. |
| `GIGSIM_LLM_MODEL`, `GIGSIM_LLM_DISABLED`, `GIGSIM_LLM_TIMEOUT` | `openai/gpt-oss-20b`, unset, `20` | Client personalisation LLM. `GIGSIM_LLM_DISABLED=1` uses the heuristic (CI). |

### Data pipeline and evals

| Variable | Purpose |
|---|---|
| `KAGGLE_API_TOKEN` (or `KAGGLE_USERNAME` + `KAGGLE_KEY`, or `~/.kaggle/kaggle.json`) | `scripts/download_kaggle.py` |
| `GIGSIM_ADMIN_URL`, `GIGSIM_LABEL_USE_LLM` | `rag/ingest/proposals.py`: the GigSim instance used to label past proposals, and whether to use its LLM |
| `EVAL_GIGSIM_URL` | GigSim used by eval runners (default `http://localhost:8091`) |
| `EVAL_TPM_BUDGET`, `EVAL_MODEL_CONCURRENCY` | Per-model tokens per minute and concurrency for evals (defaults 7000 and 2, `evals/runners/common.py`) |
| `EVAL_ANTHROPIC_CAP_USD`, `EVAL_MAX_QUOTA_WAIT` | Judge spend cap and the longest wait on a quota error |
| `UPDATE_SNAPSHOTS` | `1` rewrites the MCP contract snapshots |

### Deployment

| Variable | Purpose |
|---|---|
| `HF_TOKEN`, `HF_USERNAME` | `scripts/deploy_hf.py`: Hugging Face write token and account |
| `DEPLOY_MODEL_PROFILE` | `MODEL_PROFILE` set on the Space (default `open`) |

### Web

| Variable | Purpose |
|---|---|
| `API_URL` | Where Next.js rewrites `/api/*` (`apps/web/next.config.ts`). Read at build time in the Dockerfiles. |
| `PORT`, `BIND_HOST` | Standalone server port and bind address (`apps/web/scripts/start-standalone.mjs`) |

The starter `.env.example` still lists `GIGSIM_API_TOKEN`, `LANGFUSE_PUBLIC_KEY` and
`LANGFUSE_SECRET_KEY`. No code reads them.

## 4. Seeding

| What | Command | Output |
|---|---|---|
| Full data build (Kaggle → personas → processed data → GigSim seed → eval sets → labelled past proposals) | `make seed` (`scripts/download_kaggle.py`, `build_personas.py`, `build_dataset.py`, `label_proposals.py`, `validate_data.py`) | `data/raw/`, `data/personas/`, `data/processed/` (git-ignored), `evals/datasets/`. Every LLM call is cached in `data/cache/llm/`, so a rerun costs no tokens. See `docs/DATA_CARD.md` §9. |
| Validate data only | `make validate-data` | Report on stdout |
| Compact deploy seed | `python scripts/make_deploy_seed.py [--open-jobs 600 --stream-jobs 900 --special-jobs 150 --seed 7]` | `data/deploy_seed/` (committed): open jobs, stream jobs and every sampled scam, injection or duplicate, with their clients. Copies `gigsim/fixtures/` if the full seed is missing. |
| Reset GigSim | `curl -X POST localhost:8081/admin/reset -H "X-Admin-Token: $GIGSIM_ADMIN_TOKEN"` | Drops and re-seeds, clock back to 0 |
| App tables | automatic: `common/db.py` `migrate()` on API and worker startup | |

### Evaluations

```bash
make eval-gigsim                  # eval GigSim on :8091: dev seed, no chaos, no rate limit, heuristic client LLM
make eval                         # every runner, then scripts/make_results_table.py → evals/results/tables.md
make eval-smoke                   # 30-job smoke run; evals/runners/check_thresholds.py gates CI on it
make eval EVAL_PROFILE=open       # the default EVAL_PROFILE is paid (Claude Haiku); open runs on Groq
```

Every LLM call made by the runners is cached in `data/cache/evals/`, so a rerun only pays for what
is missing. Results land in `evals/results/*.json`, each with `generated_at`, the git SHA and a
config snapshot.

## 5. Reviewer login

On startup the API runs `apps/api/service.py` `seed_reviewer()`. If `REVIEWER_PASSWORD` is set
and no user has `REVIEWER_EMAIL`, it creates user `u_reviewer` with an argon2 hash of that
password. The user is onboarded on the `ai_ml` persona with the GigSim token `gigsim-token-ai`
and three saved searches: "machine learning", "rag llm", "data pipeline".

- The password lives only in the deployment's secrets (Space secret `REVIEWER_PASSWORD`) and is
  given to the examiner in a private Classroom comment. It is never in the repo.
- Changing `REVIEWER_PASSWORD` later does not change an existing account. Delete the user row
  first (`delete from users where email='reviewer@gigbid.dev'`, which cascades to profile and
  searches).

## 6. Live-mode scouting interval and why it is conservative

`agent/config.yaml`:

```yaml
marketplace:
  scout_interval_minutes: 30          # GigSim
  live_scout_interval_minutes: 240    # Upwork live mode
  max_requests_per_minute: 40
```

`worker/tasks.py` `scheduled_scout()` runs every 15 minutes but only scouts a user whose
interval has elapsed. The interval is the smallest `interval_minutes` among the user's saved
searches (default 30, minimum 15, `SavedSearch` in `apps/api/schemas/__init__.py`). For users whose
profile `marketplace_mode` is `upwork_live`, it is raised to **at least 240 minutes**. That is
at most 6 scheduled scouts a day. Each scout runs one search per saved search (up to 20 results),
then `get_job` for each new job.

Why 240:

- Upwork's guidance on bots and automation treats scraping, bulk polling and proposal spam as
  violations, and says an API key does not authorise automation outside its approved use. Live
  access here goes only through Upwork's official MCP server, and every write is a draft the user
  confirms on Upwork (`mcp_servers/marketplace/adapters/upwork_live.py`).
- A freelancer who checks new jobs a few times a day does not need fresher data. A 4-hour interval
  matches that pattern and keeps the request volume far from anything that looks like scraping.
- The bid graph adds reads per job (`get_job`, `get_client_history`). Fewer scouts means fewer
  analyses, so cost and quota stay predictable.
- "Scout now" in the inbox (`POST /api/jobs/scout`) is a human action and is not throttled by the
  schedule.

Caveats: the 240-minute floor keys off the profile's `marketplace_mode`, not the global
`marketplace.mode`. In live mode `get_events` returns no events (`UpworkLiveAdapter.get_events`),
so the pipeline board does not advance from marketplace events.

## 7. Degraded-mode drill: kill the Marketplace MCP server

Run with the Arq worker (compose, or §1 with `REDIS_URL`), because recovery is the `retry_queued`
cron job.

```bash
# compose
docker compose -f infra/docker-compose.yml stop mcp-marketplace
# local, Linux or macOS
pkill -f mcp_servers.marketplace.server
# local, Windows PowerShell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? CommandLine -match 'mcp_servers.marketplace' | % { Stop-Process -Id $_.ProcessId }
```

What you should see:

1. Within 20 s the amber banner appears on every page: "Marketplace unavailable: work is queued
   and will resume automatically", listing `mcp_marketplace (down)`
   (`apps/web/src/components/DegradedBanner.tsx`, polling `GET /api/health`).
2. Click **Analyze** on a job. The run is created and stays `queued`: `apps/api/runs.py`
   `execute()` sees no marketplace tools and refuses to start. A row appears in `work_queue`, and
   the banner shows the queued count. If the server dies in the middle of a run instead, the run
   viewer also shows the event "marketplace unavailable: … queued for retry".
3. Endpoints that need the marketplace synchronously, such as opening a message thread, return
   503 `{"error": "marketplace_unavailable", "queued": n}`, which also raises the banner.
4. Restart the server (`docker compose ... start mcp-marketplace`, or rerun
   `python -m mcp_servers.marketplace.server`). Within about a minute `/api/health` is `ok`, the
   banner clears, and `retry_queued` replays the queued run, which continues normally.

Code path: `agent/mcp_client.py` (`ToolBox.http`, `AgentTools.call` → `MarketplaceUnavailable`)
→ `apps/api/runs.py` `execute()` → `worker/tasks.py` `run_start` / `_queue` / `retry_queued` →
`apps/api/service.py` `health()` → the UI banner.

On the Hugging Face Space, supervisord restarts a killed process (`autorestart=true`), so the
outage lasts only a few seconds. Run the drill locally or with compose.

## 8. Crash and resume drill (exactly-once submission)

Goal: approve a proposal, crash before the submit finishes, restart, and show one proposal and
one Connects spend.

1. Run with compose or with the Arq worker (§1). Open a job whose recommendation is "bid" and wait
   for the studio to show the approval panel. That state is a Postgres checkpoint, so it survives
   any restart: kill the API now, restart it, refresh, and the pending approval is still there.
2. Click **Approve**, then kill the worker at once:
   `docker compose -f infra/docker-compose.yml kill worker` (or Ctrl+C the `arq` process).
3. Restart it with `docker compose ... start worker`. Arq keeps a job in Redis until it completes,
   so the `run_resume` job runs again. After a graceful stop it runs at once. After a hard kill it
   runs once its in-progress lock expires, which is bounded by `job_timeout` (900 s,
   `worker/main.py`). The thread resumes from its last checkpoint and `submit` runs again with
   the same keys from `idem_key()`.
4. Prove it ran once:

```sql
-- one row per tool for this draft
select tool, key, at from idempotency where user_id='u_reviewer' order by at desc limit 4;
-- a second submit_proposal call is logged as a replay
select at, tool, result from audit_log where tool in ('create_proposal_draft','submit_proposal')
order by id desc limit 6;
```

```bash
curl -s localhost:8081/v1/proposals -H "Authorization: Bearer gigsim-token-ai"   # one proposal for the job
curl -s localhost:8081/v1/connects  -H "Authorization: Bearer gigsim-token-ai"   # balance dropped once
```

In inline mode (`scripts/dev.py` without Redis), killing the API also kills the in-flight task
and nothing re-queues it. If the crash happened after the approval checkpoint, the thread waits at
`submit` with no interrupt, and the UI shows no pending approval. Use the Arq setup for this drill.

## 9. Switching between GigSim and live Upwork mode

Precedence in `mcp_servers/marketplace/server.py` `adapter_for()`: the user's profile
`marketplace_mode` comes first, then `agent/config.yaml` `marketplace.mode`, which
`MARKETPLACE_MODE` overrides.

- **Per user (normal path):** Settings → Connected accounts → connect Upwork (OAuth through
  `/api/oauth/upwork/start`), then Settings → Profile and model → set the marketplace to Upwork. `PUT /api/profile` refuses
  `upwork_live` until a token exists (409).
- **Default for users with no saved profile:** `marketplace.mode: upwork_live` in
  `agent/config.yaml`, or `MARKETPLACE_MODE=upwork_live`. Every onboarded profile stores its own
  `marketplace_mode` (default `gigsim`), which takes precedence.
- **Then restart the Marketplace MCP server.** It caches one adapter per user in memory (`_adapters`).
- Live mode needs `PUBLIC_BASE_URL` set to the public HTTPS origin, because the OAuth redirect URI
  and client ID metadata document are built from it.
- Nothing under `agent/` changes. The graphs see the same MCP tool names. What changes: the
  adapter behind the tools, the Connects cost (shown on Upwork instead), `submit_proposal` (returns
  `draft_awaiting_confirmation_on_upwork` and spends nothing), and the scouting interval (§6).

## 10. Injecting hidden-test jobs into GigSim

`POST /admin/import` adds jobs and clients at runtime, in the seed format of
`docs/specs/GIGSIM_SPEC.md`. Jobs need `job_id`, `title` and `client_id`. Clients need
`client_id` and `name`. Every job's client must exist or be in the same request.

```bash
curl -X POST http://localhost:8081/admin/import \
  -H "X-Admin-Token: $GIGSIM_ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"clients":[{"client_id":"hc_001","name":"Acme Ltd","total_spent":12000,"payment_verified":true,
        "hidden":{"must_have_skills":["python","rag"],"budget_ceiling_factor":1.0,"max_words":220,"responsiveness":0.7}}],
       "jobs":[{"job_id":"hidden_001","client_id":"hc_001","title":"RAG chatbot over PDFs",
        "description":"...","category":"ml_ai","skills":["python","rag"],"budget":800,"is_hourly":false}]}'
```

- Jobs release immediately (or at `now + release_minute`) and emit `job_posted` events.
  Duplicate `job_id`s return 409, and an unknown client returns 422.
- GigBid finds them through saved searches. A job reaches the inbox only if it matches a saved
  search query of the reviewer account, so add an empty-query search in Settings for a hidden-test
  run. New jobs arrive at the next scheduled scout (within the 30-minute interval) or at once with
  **Scout now**.
- `worker/tasks.py` `scout_user()` auto-analyses only the first 5 new jobs per scout run
  (`profile.get("auto_analyse_limit", 5)`). The rest wait in the inbox for **Analyze**.
- **On the Hugging Face Space, GigSim listens on 127.0.0.1 only and `/admin` is not exposed**
  (only port 7860 is public, and Next.js rewrites only `/api/*`). An examiner cannot reach
  `/admin/import` on the deployed URL as built:
  `{{ADMIN_IMPORT_URL: public route to GigSim /admin/import on the Space, if one is added}}`.
  Locally and in compose, port 8081 is published.

## 11. Rate limits and the Groq free tier

| Limit | Value | Where |
|---|---|---|
| GigSim per account | 60 requests/min, 429 with `Retry-After` | `GIGSIM_RATE_PER_MIN` |
| Marketplace MCP per user | 40 requests/min token bucket (burst 10) | `marketplace.max_requests_per_minute`, `common/mcp_http.py` `RateLimiter` |
| GigSim adapter retries | 3 retries with backoff on 429 / 5xx, 20 s timeout | `marketplace.max_retries`, `timeout_seconds` |
| MCP client | 30 s per call, 2 retries with backoff | `agent/mcp_client.py` |
| Graph node retries | up to 6 attempts, 5 s → 60 s backoff, only on transient errors | `agent/graphs/bid_graph.py` `RETRY` |
| Tokens per job | `budgets.max_tokens_per_job` | `agent/config.yaml` |

Groq's free tier has per-model request and token limits per minute and per day, and they change.
Check the current numbers in the Groq console before a demo or eval run. When a model is
rate-limited:

- `agent/llm.py` switches to the profile's fallback model. In `open`, the two gpt-oss models are
  separate rate-limit buckets.
- Node retries back off.
- Eval runners throttle to `EVAL_TPM_BUDGET` and stop cleanly with partial results on a daily
  quota (`DailyLimitReached`).

Several viewers at once, or a large hidden-test batch, can exhaust the daily quota. Runs then fail
over to `needs_attention` or `failed` and show it in the run viewer, rather than hanging.

## 12. Deployment (Hugging Face Space)

```bash
python scripts/deploy_hf.py      # needs HF_TOKEN and HF_USERNAME in .env
```

`scripts/deploy_hf.py` does four things:

- creates or updates the public Docker Space `<HF_USERNAME>/gigbid`;
- uploads only git-tracked files, so `.env` and raw data cannot leak, and places
  `infra/hf/Dockerfile` at the Space root;
- generates any missing `APP_SECRET_KEY`, `TOKEN_ENCRYPTION_KEY`, `MCP_AUTH_TOKEN` and
  `REVIEWER_PASSWORD`, appending them to your local `.env` without printing them;
- sets the Space secrets `DATABASE_URL`, `REDIS_URL`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`,
  `CEREBRAS_API_KEY`, `LANGSMITH_API_KEY` and the four generated values, and the variables
  `PUBLIC_BASE_URL`, `CORS_ORIGINS`, `LANGSMITH_TRACING=true`, `LANGSMITH_PROJECT=gigbid`,
  `MODEL_PROFILE` (from `DEPLOY_MODEL_PROFILE`, default `open`) and `WORKER_MODE=arq`.

`GIGSIM_ADMIN_TOKEN` is not set, so the Space's GigSim keeps the default admin token. It only
listens on 127.0.0.1, but set a real token if `/admin` is ever exposed.

- Image: `infra/hf/Dockerfile`. Processes: `infra/hf/supervisord.conf`. Public port 7860.
- Live URL: `https://gigbid-vtva.onrender.com`.
- Health: `GET https://gigbid-vtva.onrender.com/api/health`.
- Logs: the Space's container log. supervisord sends every process to stdout.

## 13. Known limitations

- **GigSim state resets when the Space restarts.** Its database is `/tmp/gigsim.sqlite`, and it
  re-seeds from `data/deploy_seed`. Postgres (Neon) keeps the app's jobs, proposals and memory,
  so after a restart the pipeline can reference GigSim proposals and threads that no longer exist.
  The active policy version also returns to `active` in `gigsim/policy.yaml`.
- **The Space sleeps** after a period without visits and takes about a minute to wake. No
  keep-alive job exists in `.github/workflows/` at the time of writing, so open the URL before a
  demo.
- **The evidence index is in process memory** (`rag/retriever.py`) and is rebuilt on first search
  after each start. Portfolio uploads are stored but not indexed (`add_user_docs()` is never called).
- **One trace id does not yet flow end to end** (ADR 0008).
- **Inline mode** has no cron jobs: no scheduled scouting, event sync or degraded-mode replay.
- **Live mode** has no event feed, so the pipeline board does not move on its own.
- **The degraded-mode drill on the Space** is short-lived, because supervisord restarts the server.
- **Workspace** is a mock: no Google Calendar or Gmail, and its writes have no idempotency keys.
- **GigSim `/admin`** is protected only by a shared header token. Keep `GIGSIM_ADMIN_TOKEN`
  secret, and never expose `/admin` without it.


## Live Upwork mode: status (15 Nov 2026)

Tried end to end from the public URL. Upwork's authorization server fetched our client ID metadata document
(`/api/oauth/upwork/client-metadata.json`, HTTP 200) and, after the user signed in, answered
"Client not found or disabled". Upwork does not accept self-hosted MCP clients this way, so live mode needs a
registered Upwork API key (`UPWORK_CLIENT_ID`, `UPWORK_CLIENT_SECRET`, fixed redirect URI). Evidence:
`evals/results/upwork_live.json`. GigSim mode is unaffected.

## Hosted deployment (Render, single container)

Live URL: https://gigbid-vtva.onrender.com (reviewer login `reviewer@gigbid.dev`; the password is the
`REVIEWER_PASSWORD` secret, shared privately). Hugging Face withdrew free Docker Spaces, so the app runs on
Render's free web service from `infra/render/Dockerfile`, deployed by `scripts/deploy_render.py`.

Render's free tier has 512 MB of RAM, so this deployment runs in single-container mode:
- one Python process serves the API, the three MCP servers in-process (`GIGBID_INPROCESS_MCP=1`, same MCP
  protocol over in-memory streams) and GigSim mounted at `/gigsim` (`GIGSIM_MOUNT=1`);
- the Arq worker's schedules are replaced by a timer in the API (`apps/api/sim_ticker.py`);
- retrieval uses `v2_hybrid` (`RAG_VARIANT`) so the cross-encoder model is not loaded; the evaluated, shipped
  variant (`v8_corrective`) runs in the full deployment (`infra/docker-compose.yml`);
- models: the Claude Haiku profile (`MODEL_PROFILE=paid`), because Groq's free tier caps daily tokens.

Known limits: the free instance sleeps after 15 idle minutes (about a minute to wake) and GigSim state resets on
restart. **Starting a new analysis exceeds 512 MB**: Render's event log shows `oomKilled` (limit 512Mi) when the Fit
Matcher loads the embedding model, and the instance restarts. Browsing existing jobs, drafts, runs and traces works.
The full system runs locally (below) or on a 2 GB instance without changes.


## Run everything locally (viva / demo)

One command from the repo root, in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_local.ps1
```

The first run creates `.venv-local` (Python 3.12 via uv) and installs the web dependencies; later runs start in
seconds. It starts GigSim, the three MCP servers, the API (inline worker) and the web app as separate processes.
Open http://localhost:3000 and sign in as `reviewer@gigbid.dev` (password: `REVIEWER_PASSWORD` in `.env`). Logs are
in `data/cache/logs/`. Ctrl+C stops everything. Needs `.env` (Neon `DATABASE_URL`, `ANTHROPIC_API_KEY`, optional
`GROQ_API_KEY`, `LANGSMITH_API_KEY`), Python 3.11+ on PATH and Node 22.
