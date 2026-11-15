# ADR 0008: LangSmith for tracing

- Status: accepted, trace-id propagation incomplete (see Consequences)
- Plan reference: D26 in `PLAN.md`

## Context

E3 requires one trace id from the UI request through the API, the graph, every MCP server and the
audit log, with tokens and cost per node. The README needs three public trace links. There is no
VM for a self-hosted stack.

## Decision

LangSmith, free developer tier, enabled through environment variables only (`LANGSMITH_TRACING`,
`LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`; set in `infra/docker-compose.yml`). LangGraph and
LangChain trace automatically.

Alongside it, GigBid keeps its own records, which do not depend on LangSmith:

- `audit_log` (append-only, PII-masked, with `trace_id`) for every MCP tool call
  (`common/mcp_http.py` `audit()`; the trace id arrives as the `X-Trace-Id` header set in
  `agent/mcp_client.py` `connections()`);
- `run_events` and `runs` (tokens, USD, latency, per-node usage from `agent/llm.py` `Usage`).

## Alternatives rejected

- **Self-hosted Langfuse v3.** Needs ClickHouse, Redis and S3, too heavy without a VM.
- **Arize Phoenix.** Light, but no easy public share links. Kept as the documented fallback if
  the LangSmith trace cap is hit.

## Consequences

- Public share links come from the LangSmith UI. Bulk eval runs switch tracing off
  (`evals/runners/common.py` sets `LANGSMITH_TRACING=false` by default) to stay under the
  free-tier cap.
- **Gap.** One id does not yet flow end to end. `apps/api/main.py` creates a request trace id;
  `apps/api/runs.py` `execute()` creates a different one per graph step, which is the id the MCP
  servers and `audit_log` see; and `new_run()` stores a link built from a third id. Graph runs are
  not tagged with `trace_id` metadata, so the "View trace" link filters on metadata that is not
  set. The fix is to create the id once in `new_run()`, pass it to `execute()`, and add
  `{"metadata": {"trace_id": ...}}` to `bid_graph.graph_config()`.
- Tokens and cost per node are visible in our own `runs.usage.by_node`, whatever LangSmith shows.
