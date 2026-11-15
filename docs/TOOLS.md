# MCP tool inventory

Every capability the agents use is an MCP tool. The annotations and schemas below come from the
contract snapshots in `tests/contract/snapshots/{marketplace,portfolio,workspace}.json`, which
`tests/contract/test_tool_schemas.py` compares against the live servers. CI fails when a tool
signature changes unintentionally. To accept an intended change, regenerate the snapshots with
`UPDATE_SNAPSHOTS=1`.

All three servers are built with the official MCP Python SDK (`mcp.server.fastmcp.FastMCP`), run
over Streamable HTTP (`stateless_http=True`, `json_response=True`) and sit behind
`common/mcp_http.py` `BearerAuthMiddleware`. That middleware rejects requests without
`Authorization: Bearer $MCP_AUTH_TOKEN` and reads the user from `X-GigBid-User` and the trace id
from `X-Trace-Id`. Every call is written to the append-only, PII-masked `audit_log` table.

## 1. Our tools

Columns: R/W = read or write. RO / Destr / Idem = `readOnlyHint` / `destructiveHint` /
`idempotentHint`. Every marketplace tool also has `openWorldHint=true`, and every portfolio and
workspace tool has `openWorldHint=false`. Every tool declares an output schema.

### Marketplace server: `mcp_servers/marketplace/server.py` (port 8101)

Auth for all rows: bearer token, plus a per-user token bucket of `marketplace.max_requests_per_minute`
(40) from `agent/config.yaml`, kept below GigSim's 60 per minute per account.

| Tool | R/W | RO | Destr | Idem | Notes |
|---|---|---|---|---|---|
| `search_jobs` | R | true | false | true | `query` ≤ 200 chars, `category`, `limit` 1–50, `offset`, `posted_after`. Returns summaries with a 280-char snippet. |
| `get_job` | R | true | false | true | Full post, screening questions, `connects_cost`, `proposals_count`. The description says the text is untrusted. |
| `get_client_history` | R | true | false | true | Spend, hires, hire rate, rating, payment verification, reviews. |
| `get_connects_balance` | R | true | false | true | Balance and weekly allowance. |
| `get_market_stats` | R | true | false | true | p25/p50/p75 posted hourly and fixed prices, plus realised hourly (K4). |
| `get_policy` | R | true | false | true | Rules, Connects formula, `required_disclosure` (the change request's channel). |
| `list_proposals` | R | true | false | true | Status: submitted, viewed, replied, interview, hired, declined. |
| `list_threads` | R | true | false | true | Client message threads. |
| `list_messages` | R | true | false | true | Messages in a thread. The description says client text is untrusted. |
| `get_events` | R | true | false | true | Cursor feed: job_posted, proposal_viewed, client_replied, interview_requested, hired, declined. |
| `create_proposal_draft` | W | false | false | true | `draft: ProposalDraftIn` (cover letter 40–5000 chars, ≤ 10 answers of ≤ 2000 chars, `bid_amount` > 0 and ≤ 100000, `rate_type` hourly or fixed), `idempotency_key` 8–128 chars, `dry_run`. Sends nothing and spends no Connects. |
| `submit_proposal` | W | false | **true** | true | `draft_id`, `idempotency_key`, `dry_run`. Spends Connects. In live mode it never submits and returns `draft_awaiting_confirmation_on_upwork`. |
| `send_message` | W | false | false | true | `thread_id`, `text` 1–4000 chars, `idempotency_key`, `dry_run`. In live mode it only creates a draft message on Upwork. |

Write tools go through `_write()`, which:

- stores `(user_id, tool, key) → request hash + response` in the `idempotency` table;
- replays the stored response for a repeated key with the same content;
- rejects a reused key with different content (`idempotency_conflict`);
- never stores a dry run.

Resource templates and prompts: none.

### Portfolio server: `mcp_servers/portfolio/server.py` (port 8102, or stdio)

Auth: bearer token over HTTP. Over stdio (`python -m mcp_servers.portfolio.server --stdio`) there
is no auth; the server is local to the host app (Claude Desktop, Cursor). `PORTFOLIO_PERSONA` and
`GIGBID_PERSONAS_DIR` point it at a portfolio folder.

| Tool | R/W | RO | Destr | Idem | Notes |
|---|---|---|---|---|---|
| `search_evidence` | R | true | false | true | `requirement` 2–2000 chars, `k` 1–20, `filters` (types, outcomes, since), `persona_id`. Returns `EvidenceItem`s with id, type, source, date, outcome and score. Retrieval variant from `rag.variant`. |
| `get_case_study` | R | true | false | true | `evidence_id` matching `^[a-z_]+:[a-z]+:.+$`. Full text and metadata. |
| `list_skills` | R | true | false | true | Skills with the number of evidence items mentioning each. |

Resource templates: `portfolio://case/{evidence_id}`, `portfolio://proposal/{evidence_id}`,
`portfolio://profile/{persona_id}`. Prompts: `answer_screening_question`, `fit_for_job`,
`cover_letter_outline`.

### Workspace server: `mcp_servers/workspace/server.py` (port 8103)

Auth: bearer token. Backend: a local mock (the `workspace_items` table plus a working-hours
calendar from 09:00 to 18:00 on weekdays), not Google Calendar or Gmail. The three functions
marked `BACKEND` are the swap points.

| Tool | R/W | RO | Destr | Idem | Notes |
|---|---|---|---|---|---|
| `free_slots` | R | true | false | true | `days_ahead` 1–14, `duration_minutes` 15–180, `timezone`, `max_slots` 1–10. Avoids existing holds. |
| `create_interview_hold` | W | false | false | **false** | Tentative hold. No idempotency key, so repeating it creates a second hold. Not called by the current graphs. |
| `create_email_draft` | W | false | false | **false** | Saves a draft and never sends. No idempotency key. Not called by the current graphs. |

## 2. Per-agent allowlists (`agent/mcp_client.py` `ALLOWLIST`)

`ToolBox.for_agent(name)` filters tools by name. `AgentTools.call()` raises `PermissionError` for
anything else.

| Agent key | Used in | Tools | Holds a write tool? |
|---|---|---|---|
| `scout` | `worker/tasks.py` `scout_user()` → `agent/nodes/scout.py` | `search_jobs`, `get_events` | no |
| `intake` | bid graph `intake`, `scout_user()` | `get_job` | no |
| (Job Analyst) | `agent/nodes/analyst.py` | none: it never asks for tools | no |
| `risk_assessor` | `agent/nodes/risk_assessor.py` | `get_client_history` | no |
| `fit_matcher` | `agent/nodes/fit_matcher.py` | `search_evidence`, `get_case_study` | no |
| `pricing` | `agent/nodes/pricing.py` | `get_market_stats`, `get_connects_balance`, `get_policy` | no |
| `writer` | `agent/nodes/writer.py` | `search_evidence`, `get_case_study` | no |
| `verifier` | (reserved; `rag/verify.py` uses the evidence already in state) | `search_evidence` | no |
| `critic` | (reserved; the Critic uses state) | `search_evidence` | no |
| `compliance` | `agent/nodes/compliance.py` | none, by design | no |
| `submitter` | bid graph `prepare_submission` (dry run) and `submit` (after `interrupt()`) | `create_proposal_draft`, `submit_proposal`, `get_connects_balance` | **yes**, only after human approval |
| `liaison` | conversation graph `load_messages`, `find_slots` | `list_threads`, `list_messages`, `free_slots`, `create_interview_hold`, `create_email_draft` | Workspace drafts and holds only, not called today |
| `messenger` | conversation graph `send` (after `interrupt()`) | `send_message` | **yes**, only after human approval |
| `tracker` | `worker/tasks.py` `sync_events()` | `list_proposals`, `get_events`, `list_threads` | no |

Known exception: `agent/graphs/conversation_graph.py` `draft_reply()` calls `search_evidence`
directly from `ctx.toolbox.tools`, outside the `liaison` allowlist. It is read-only.

Client discipline, all in `agent/mcp_client.py`: a 30 s timeout per call
(`asyncio.wait_for`), 2 retries with exponential backoff and jitter on connection errors,
`Retry-After`-aware sleeps on `rate_limited`, and `MarketplaceUnavailable` when the marketplace
server is unreachable (degraded mode, `docs/ARCHITECTURE.md` §8).

## 3. Third-party MCP servers

| Server | Endpoint | Auth | Used for | Trust rationale |
|---|---|---|---|---|
| **Upwork** (official) | `https://mcp.upwork.com/mcp`, Streamable HTTP through `MultiServerMCPClient` (`mcp_servers/marketplace/adapters/upwork_live.py`) | OAuth 2.1 with PKCE (S256). Discovery through `/.well-known/oauth-protected-resource/mcp`. The `client_id` is a client ID metadata document that GigBid serves at `/api/oauth/upwork/client-metadata.json` (`client_metadata()`), unless `UPWORK_CLIENT_ID` is set. Tokens are Fernet-encrypted per user in `oauth_tokens` (`common/security.py`) and never logged (`mask_obj` redacts token keys). | Live mode: job search, job details, threads and messages (reads), proposal and message **drafts** (writes) | Run by the marketplace itself, it is the only sanctioned automated access to Upwork. Every write it offers is a draft the user confirms on Upwork, so GigBid cannot send on its own. |
| **GitHub** (official GitHub MCP server) | `github/github-mcp-server`, used read-only for repository contents | `GITHUB_TOKEN` (fine-grained, read-only contents scope), from the environment only | Ingesting a freelancer's repos (README and code) into the portfolio corpus | Maintained by GitHub and reading only through GitHub's API with a read-only token, it can see nothing beyond what that token grants and has no write path into GigBid. |

Status at the time of writing:

- **Upwork:** the adapter, OAuth flow (`/api/oauth/upwork/start`, `/callback`, `/disconnect` in
  `apps/api/routers/oauth.py`) and tool mapping are implemented. Whether the student's account
  completed the flow: `{{LIVE_MODE_STATUS: OAuth sign-in result and the tool names Upwork returned (adapter.tool_map())}}`.
- **GitHub:** the ingestion module that `rag/ingest/loaders.py` refers to
  (`rag/ingest/github_ingest.py`) is not in the tree. The persona repos under
  `data/personas/<persona>/repos/` are currently read from disk.

## 4. Running the servers on their own

```bash
python -m mcp_servers.marketplace.server      # :8101/mcp, needs GigSim and DATABASE_URL
python -m mcp_servers.portfolio.server        # :8102/mcp
python -m mcp_servers.portfolio.server --stdio
python -m mcp_servers.workspace.server        # :8103/mcp, needs DATABASE_URL
```

Ports come from `MCP_MARKETPLACE_PORT`, `MCP_PORTFOLIO_PORT`, `MCP_WORKSPACE_PORT`, and the bind
address from `MCP_HOST` (default 127.0.0.1). To inspect a server, run
`npx @modelcontextprotocol/inspector`, connect to `http://127.0.0.1:8102/mcp` and add the header
`Authorization: Bearer <MCP_AUTH_TOKEN>`.
