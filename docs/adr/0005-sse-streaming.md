# ADR 0005: Server-Sent Events for live run progress

- Status: accepted
- Plan reference: D24 in `PLAN.md`

## Context

The run viewer must show node-by-node progress, so the user never stares at a spinner. A page
refresh must not lose progress or a pending approval. Progress flows server → browser. Approvals
are ordinary POSTs.

## Decision

SSE at `GET /api/runs/{run_id}/stream` (`apps/api/service.py` `stream_run()`, served with
`sse_starlette.EventSourceResponse`).

- Every node emits start / end / error / custom events through the `@node` decorator
  (`agent/nodes/common.py`) into the `run_events` table (`apps/api/runs.py` `_emitter()`).
- The stream polls `run_events` from the last sequence number and honours `Last-Event-ID`, so a
  reconnect resumes where it left off. It closes after a terminal status (`done`, `interrupted`,
  `failed`, `needs_attention`).
- The browser side is `apps/web/src/lib/hooks/useRunStream.ts` and
  `apps/web/src/components/RunTimeline.tsx`.

## Alternatives rejected

- **WebSockets.** Two-way traffic is not needed, they are harder to proxy, and they have no
  built-in resume.
- **Streaming LangGraph `astream` straight through the HTTP response.** Runs execute in the
  worker, not in the request process, so there is no in-process stream to forward. Persisting
  events also gives the run viewer a history.

## Consequences

- Runs survive the browser going away, and the timeline is replayable.
- Up to 0.6 s of polling latency per event (`asyncio.sleep(0.6)`), plus database load
  proportional to open viewers. That is fine at this scale.
- `next.config.ts` disables compression so proxies do not buffer the stream.
- The brief names a module `apps/api/streaming.py`. The bridge lives in `service.py` instead.
