# GigSim

A standalone marketplace simulator (a fake Upwork) for GigBid development and evals. The full
specification is `docs/specs/GIGSIM_SPEC.md`. GigSim never imports GigBid code, and GigBid talks
to it only over HTTP.

## Run

```bash
uvicorn gigsim.app:app --port 8081
.venv/Scripts/python -m pytest gigsim/tests -q
```

On first start, the SQLite DB is created and seeded from `GIGSIM_SEED_DIR` (if it has
`jobs.jsonl` and `clients.jsonl`), or from the built-in `gigsim/fixtures/` otherwise. Fixture
accounts are `acct_ai`, `acct_web` and `acct_data`, with tokens `gigsim-token-ai`,
`gigsim-token-web` and `gigsim-token-data`.

```bash
curl -H "Authorization: Bearer gigsim-token-ai" "localhost:8081/v1/jobs?q=rag"
curl -X POST -H "X-Admin-Token: gigsim-admin" -H "Content-Type: application/json" \
     -d '{"minutes": 120}' localhost:8081/admin/clock/advance
```

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `GIGSIM_DB` | `data/cache/gigsim.sqlite` | SQLite file |
| `GIGSIM_SEED_DIR` | `data/processed/gigsim_seed` | Seed dir (falls back to `gigsim/fixtures/`) |
| `GIGSIM_ADMIN_TOKEN` | `gigsim-admin` | `X-Admin-Token` for `/admin/*` |
| `GIGSIM_RATE_PER_MIN` | `60` | Token bucket per account (`<=0` disables it) |
| `GIGSIM_ERROR_RATE` | `0.02` | Share of `/v1` requests that return 503 (deterministic) |
| `GIGSIM_START` | `2024-02-20T09:00:00Z` | Sim time at minute 0 |
| `GIGSIM_CLOCK_SPEED` | `0` | Sim minutes per real minute (0 = manual only) |
| `GIGSIM_SEED` | `42` | RNG seed for chaos and the client model |
| `GROQ_API_KEY` | unset | Enables LLM personalisation and replies (cached in `llm_cache`) |
| `GIGSIM_LLM_MODEL` | `openai/gpt-oss-20b` | Groq model id |
| `GIGSIM_LLM_DISABLED` | unset | `1` forces the heuristic and template fallbacks (tests set this) |
| `GIGSIM_LLM_TIMEOUT` | `20` | Seconds per Groq call |

`.env` is loaded if present. Without a key, everything works through the heuristic fallbacks.

## Endpoints

`/v1/*` requires `Authorization: Bearer <account token>`. POSTs require an `Idempotency-Key`
header, and a replayed response carries `Idempotent-Replay: true`. Every error body is
`{"error", "detail", ...}`.

| Endpoint | Purpose |
|---|---|
| `GET /v1/jobs?q=&category=&skills=&posted_after=&limit=&offset=` | Search released jobs (summaries with `snippet`) |
| `GET /v1/jobs/{id}` | Full job + `posted_at`, `connects_cost`, `proposals_count` |
| `GET /v1/clients/{id}` | Public client profile with `hire_rate` |
| `GET /v1/connects` | `{balance, weekly_allowance, resets_at}` |
| `GET /v1/market/stats?category=` | Rate/budget quantiles (`_all` by default) |
| `GET /v1/policy` | Active policy, Connects formula, required disclosure |
| `POST /v1/proposals/drafts` | Create a draft |
| `POST /v1/proposals/drafts/{id}/submit?dry_run=` | Policy check, spend Connects, decide the outcome |
| `GET /v1/proposals?status=` | Proposals (only revealed status) |
| `GET /v1/threads`, `GET/POST /v1/threads/{id}/messages` | Client conversations |
| `GET /v1/events?after=&limit=` | Event feed with an integer cursor |
| `POST /admin/reset` `{seed?}` | Drop and re-seed, clock to 0 |
| `POST /admin/clock/advance` `{minutes}` | Release jobs and reveal due events |
| `POST /admin/policy` `{version}` | Switch `v1` / `v2` |
| `GET /admin/jobs/{id}/truth` | Hidden labels and client prefs |
| `POST /admin/score` | Stateless, deterministic client-model score |
| `GET /admin/proposals/{id}/outcome` | Final outcome and full event schedule |
| `GET /health` | Liveness (no auth) |

## Layout

`app.py` (routes, guards) · `service.py` (business logic) · `db.py` · `seed.py` · `clock.py` ·
`policy.py` + `policy.yaml` · `client_model.py` · `llm.py` · `config.py` · `fixtures/` · `tests/`
