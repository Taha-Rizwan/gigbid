# GigSim: marketplace simulator specification (v1.0)

GigSim is a standalone FastAPI service under `gigsim/`. It stands in for Upwork in development and
evaluation. GigBid talks to it **only over HTTP**, through the marketplace MCP server. GigBid code
never imports `gigsim`, and `gigsim` never imports GigBid code (`agent/`, `rag/`, `apps/`,
`mcp_servers/`). After `v1.0` is tagged, CI fails if anything under `gigsim/` changes.

Run it with `uvicorn gigsim.app:app --port 8081`.

## Storage and seed data

- SQLite file at `GIGSIM_DB` (default `data/cache/gigsim.sqlite`). It's created and seeded on
  startup if missing. `POST /admin/reset` re-seeds it.
- Seed directory: `GIGSIM_SEED_DIR` (default `data/processed/gigsim_seed/`). If that directory is
  missing, seed from `gigsim/fixtures/` instead: a small built-in set with about 30 jobs, 15
  clients and 3 accounts, so tests and CI work with no downloaded data.
- Seed files (JSON Lines, one object per line):
  - `jobs.jsonl`: `{job_id, title, description, category, skills[], is_hourly, hourly_low,
    hourly_high, budget, country, client_id, release_minute (int, <=0 means already open at
    start), proposals_count, screening_questions[], experience_level, is_scam (bool, hidden),
    has_injection (bool, hidden), duplicate_of (job_id|null), source ("kaggle_k1"|"synthetic"|...)}`
  - `clients.jsonl`: `{client_id, name, country, member_since, total_spent, jobs_posted, hires,
    avg_rating, payment_verified, reviews:[{rating, text}], hidden:{must_have_skills[],
    budget_ceiling_factor, dislikes_generic (bool), max_words, prefers_questions (bool),
    responsiveness (0..1), is_scammer (bool)}}`
  - `accounts.jsonl`: `{account_id, name, title, hourly_rate, skills[], success_score (0..1),
    token, connects_balance, weekly_allowance}`. These are the freelancer accounts, one per persona.
  - `market_stats.json`: `{category: {hourly:{p25,p50,p75,n}, fixed:{p25,p50,p75,n},
    realised_hourly:{p25,p50,p75,n}}}`
  - `competitors.json`: `{quality_quantiles: [21 floats from 0..1]}`, the distribution of
    competing bid quality.
- **Hidden fields** (`is_scam`, `has_injection`, `hidden`) are **never** returned by `/v1`
  endpoints. Only `/admin` endpoints may expose them.

## Auth and limits

- `/v1/*`: `Authorization: Bearer <account token>`. The token identifies the freelancer account.
  An unknown token returns 401.
- `/admin/*`: `X-Admin-Token: <GIGSIM_ADMIN_TOKEN>` (env, default `gigsim-admin`).
- Rate limit: a token bucket per account, `GIGSIM_RATE_PER_MIN` (default 60). When exceeded, return
  429 with a `Retry-After` header in seconds and the body
  `{"error":"rate_limited","retry_after":n}`.
- Chaos: `GIGSIM_ERROR_RATE` (default 0.02). That fraction of `/v1` requests return
  `503 {"error":"upstream_unavailable"}`, chosen deterministically from
  `hash(seed, request_counter)`. Set it to `0` in tests. Admin endpoints are never affected.
- Every error body is `{"error": code, "detail": str}`.

## Clock

- Simulated time starts at `GIGSIM_START` (default `2024-02-20T09:00:00Z`) plus elapsed sim
  minutes.
- `GIGSIM_CLOCK_SPEED` (sim minutes per real minute, default 0 meaning manual only). When it's
  above 0, a background task advances the clock. The deployed demo uses 10.
- Advancing the clock does two things:
  - It releases jobs whose `release_minute <= now` and emits `job_posted` events.
  - It reveals scheduled outcome events whose time has come.

## Endpoints (`/v1`)

| Method and path | Purpose |
|---|---|
| `GET /v1/jobs?q=&category=&skills=&posted_after=&limit=20&offset=0` | Search released jobs. `q` matches words in the title and description. Returns `{jobs:[JobSummary], total}`. JobSummary is the job without the long description (keep the first 280 characters as `snippet`). |
| `GET /v1/jobs/{job_id}` | Full job: all public fields + `posted_at` + `connects_cost` (policy formula) + `proposals_count`. 404 if not released. |
| `GET /v1/clients/{client_id}` | Public client profile: name, country, member_since, total_spent, jobs_posted, hires, hire_rate, avg_rating, payment_verified, reviews. |
| `GET /v1/connects` | `{balance, weekly_allowance, resets_at}` |
| `GET /v1/market/stats?category=` | The `market_stats` entry for the category (or `"_all"`). |
| `GET /v1/policy` | `{version, rules:[str], connects_formula:str, required_disclosure:str|null}` |
| `POST /v1/proposals/drafts` | Body `{job_id, cover_letter, screening_answers[], bid_amount, rate_type:"hourly"|"fixed"}`. **Requires an `Idempotency-Key` header** (otherwise 400). The same key with the same account returns the original response with header `Idempotent-Replay: true`. Returns `{draft_id, job_id, status:"draft", connects_cost, created_at}`. |
| `POST /v1/proposals/drafts/{draft_id}/submit?dry_run=false` | Requires `Idempotency-Key`. With `dry_run=true`: returns `{would_send:{...full payload}, connects_cost, balance_after, policy_check:{ok, violations[]}}` and changes nothing. Otherwise: validates policy (422 `policy_violation` with `violations[]`), checks balance (402 `insufficient_connects`), spends Connects, creates a proposal, computes the outcome (below) and schedules events. Returns `{proposal_id, status:"submitted", connects_spent, balance}`. Repeating with the same key never spends twice. |
| `GET /v1/proposals?status=` | The account's proposals: `{proposal_id, job_id, job_title, status, bid_amount, submitted_at, updated_at, thread_id|null}`. Status is one of submitted, viewed, replied, interview, hired, declined. It only reflects events already revealed. |
| `GET /v1/threads` | Message threads for the account: `{thread_id, proposal_id, job_id, client_id, client_name, last_message_at, unread}`. |
| `GET /v1/threads/{thread_id}/messages` | `{messages:[{message_id, sender:"client"|"freelancer", text, sent_at}]}` |
| `POST /v1/threads/{thread_id}/messages` | Requires `Idempotency-Key`. Body `{text}`. Freelancer message. Policy-checked (422 on off-platform contact). Schedules a client reply 5–60 sim minutes later if the outcome allows it. |
| `GET /v1/events?after=<cursor>&limit=100` | `{events:[{event_id(int cursor), type, at, job_id?, proposal_id?, thread_id?, data}], next_cursor}`. Types: `job_posted, proposal_viewed, client_replied, interview_requested, hired, declined`. |

## Admin (`/admin`), used by evals and tests only

| Method and path | Purpose |
|---|---|
| `POST /admin/reset` `{seed?:int}` | Drop and re-seed. Resets the clock to 0. |
| `POST /admin/clock/advance` `{minutes:int}` | Returns `{now, released_jobs, revealed_events}`. |
| `POST /admin/policy` `{version:"v1"\|"v2"}` | Switch the active policy (the change request). |
| `GET /admin/jobs/{job_id}/truth` | Hidden labels: `is_scam, has_injection, client hidden prefs`. |
| `POST /admin/score` `{job_id, cover_letter, screening_answers[], bid_amount, rate_type, account_id}` | **Stateless.** Runs the client decision model and returns `{outcome:"ignored"|"viewed"|"replied"|"interview"|"hired", p_reply, p_hire, components:{...}}`. Deterministic for the same input. Used to label past proposals and for fast reply-rate evals. |
| `GET /admin/proposals/{proposal_id}/outcome` | The final outcome, including parts not yet revealed. |

## Policy (`gigsim/policy.yaml`)

```yaml
active: v1
versions:
  v1:
    rules: [no off-platform contact or payment, no fabricated experience, no guarantees, fair use of automation]
    connects: {base: 2, per_100_usd: 1, max: 16, hourly_equiv_hours: 20}
    required_disclosure: null
    extra_connects_if_proposals_over: null
  v2:   # the "platform policy update" (change request)
    rules: [... v1 rules ..., proposals must include the AI-assistance disclosure sentence]
    connects: {base: 2, per_100_usd: 1, max: 16, hourly_equiv_hours: 20}
    required_disclosure: "This proposal was drafted with AI assistance and reviewed by me."
    extra_connects_if_proposals_over: {threshold: 20, extra: 4}
```

**Connects cost formula:**
- `value = budget` for fixed-price jobs, or `hourly_high * hourly_equiv_hours` for hourly jobs.
- `cost = min(max, base + floor(value/100) * per_100_usd)`.
- Under v2, add `extra` when `proposals_count > threshold`.

**Policy check on submit and messages:**
- Reject off-platform contact or payment (regex for emails, phones, whatsapp, telegram, skype,
  paypal/crypto/wire).
- Reject guarantees ("guarantee", "100%", "risk-free").
- Under v2, also reject when the required disclosure sentence is missing.

## Client decision model (`gigsim/client_model.py`)

The outcome is computed once, at submit (or `/admin/score`), and is deterministic. RNG seed =
`hash(GIGSIM_SEED, job_id, account_id, sha256(cover_letter + answers + bid))`.

Components, each in 0..1:

1. **skill_coverage**: the share of the client's `hidden.must_have_skills` mentioned in the letter or
   answers. Case-insensitive, with a small synonym map (js↔javascript, postgres↔postgresql,
   sklearn↔scikit-learn, ml↔machine learning, ...).
2. **price_fit**: `ceiling = (budget or hourly_high) * budget_ceiling_factor`.
   - `bid <= ceiling`: `1 - 0.4 * bid/ceiling`.
   - Above ceiling: `max(0, 0.6 - 2*(bid/ceiling - 1))`.
   - If there's no budget: 0.6.
3. **opening**: 0 if the first sentence matches generic patterns ("I am writing to", "Dear hiring
   manager", "I am a highly skilled", "I have read your job", "I am excited to apply", "Hello
   sir", "I am the perfect fit"), else 1. Weighted ×2 if `dislikes_generic`.
4. **length_fit**: 1 if `words <= max_words`, otherwise decays linearly to 0 at `2*max_words`.
   Below 40 words: 0.3.
5. **specificity**: a rule score for concrete evidence: numbers or metrics, named tools from the
   job's skills, references to a past project ("built", "shipped", "delivered", "case study"),
   and whether it answers each screening question (answers non-empty and longer than 15 words).
6. **personalisation**: an LLM rating from 1 to 5, mapped to 0..1. It asks whether the letter
   addresses this specific client's problem. Use Groq (`GROQ_API_KEY`, model from
   `GIGSIM_LLM_MODEL`, default `llama-3.1-8b-instant`) via plain `httpx` against Groq's
   OpenAI-compatible endpoint. **Cache** the result in a SQLite table `llm_cache(hash PRIMARY KEY,
   value)`. If there's no key or the call fails, fall back to a heuristic: the share of
   distinctive job-title and description nouns found in the letter.
7. **profile**: the account's `success_score`.

**Combining them:**
- `quality = 0.22*skill + 0.15*price + 0.13*opening_w + 0.10*length + 0.18*specificity + 0.17*personalisation + 0.05*profile`,
  normalised to 0..1.
- Competitors: `n = proposals_count`. Sample `n` competitor qualities from
  `competitors.quality_quantiles` (interpolated) with the seeded RNG.
- `rank_pct` = the share of competitors we beat.
- `p_view = 0.35 + 0.6*responsiveness`
- `p_reply = sigmoid(8*(quality - 0.55)) * (0.4 + 0.6*rank_pct) * responsiveness`
- `p_interview = 0.6 * p_reply`
- `p_hire = 0.35 * p_interview * price_fit`

Then draw the outcome with the RNG: hired ⊂ interview ⊂ replied ⊂ viewed ⊂ ignored.

**Special cases:**
- Scammer clients (`is_scammer`) always "reply" with an off-platform or payment request message
  (from templates), which is what the conversation graph has to detect.
- Proposals that contain off-platform contact can't be submitted at all (422).

**Event schedule after submit:** viewed at +10..120 min. Reply at +30..600 min, and the reply text
is generated by the LLM in the client's voice (cached), with template fallback. The reply mentions
one must-have skill and asks a question. If the outcome is interview, there's an
`interview_requested` event plus a message asking for times. Hired comes 1 day after interview. Declined comes
at +3 days for ignored or viewed outcomes.

Client replies to freelancer messages: an LLM in character using the hidden prefs (cached), with
template fallback. Under negotiation the client counter-offers at 85–95% of the bid.

## Package layout

```
gigsim/
  __init__.py
  app.py            # FastAPI app factory, routers, middleware (auth, rate limit, chaos)
  db.py             # sqlite schema + helpers
  seed.py           # load seed dir or fixtures
  clock.py
  policy.py + policy.yaml
  client_model.py
  llm.py            # cached groq call with fallback
  fixtures/         # tiny built-in seed (jobs.jsonl, clients.jsonl, accounts.jsonl, market_stats.json, competitors.json)
  tests/            # pytest: idempotency, rate limit, policy v1/v2, dry_run, determinism of /admin/score, events
  README.md
```
