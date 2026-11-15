# ADR 0003: Next.js App Router for the web app

- Status: accepted
- Plan reference: D25 in `PLAN.md`

## Context

The required directory layout uses Next.js route conventions (`src/app/jobs/[id]`,
`src/app/studio/[id]`, `src/app/runs/[id]`), and the brief forbids renaming those paths. The client
must be generated from FastAPI's OpenAPI schema. Streamlit and Gradio are not accepted.

## Decision

Next.js (App Router) + TypeScript + Tailwind + TanStack Query. Pinned versions are in
`apps/web/package.json`.

- Typed client: `openapi-typescript` generates `apps/web/src/lib/api/schema.d.ts` from
  `apps/web/openapi.json` (`npm run gen:api`), and `openapi-fetch` calls it. CI fails if the
  generated file is stale (`.github/workflows/ci.yml`, step "Generated API client is up to date").
- Same-origin API: `apps/web/next.config.ts` rewrites `/api/*` to FastAPI, so the httpOnly session
  cookie is first-party and no CORS is needed. Gzip is off so SSE is not buffered.
- `output: "standalone"` so one `node server.js` serves the app in Docker and in the HF Space.
- Playwright end-to-end tests in `apps/web/tests/e2e/` (onboarding, approve, reject with reason,
  edit, degraded banner, plus inbox, run viewer, responsive and screen checks).

## Alternatives rejected

- **React + Vite.** Lighter, but the required route folders would be imitation folders with a
  client-side router underneath.
- **Hand-written fetch types.** They drift from the API. The brief requires generated types.

## Consequences

- The required paths are real routes.
- A Node build step sits in both images (`infra/docker/web.Dockerfile`, the first stage of
  `infra/hf/Dockerfile`).
- Because the browser only talks to the Next.js origin, the API is not exposed publicly in the
  Space. That is good for the attack surface, but GigSim's `/admin` routes are not reachable from
  outside either (see `docs/RUNBOOK.md`, hidden-test jobs).
