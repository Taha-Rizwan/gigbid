import type { Page, Request, Route } from "@playwright/test";
import * as fx from "./fixtures";

/**
 * Route-level mock of the GigBid API (`/api/**`), so the specs run without the
 * FastAPI backend. Handlers are keyed "METHOD /api/path/:param".
 */
export type Reply =
  | { status?: number; json?: unknown; body?: string; contentType?: string; headers?: Record<string, string> }
  | undefined;
export type Handler = (ctx: { req: Request; params: Record<string, string>; url: URL; body: unknown }) => Reply | Promise<Reply>;

export interface Recorded {
  method: string;
  path: string;
  search: string;
  body: unknown;
  contentType: string | null;
}

export function sse(events: unknown[]): Reply {
  return {
    status: 200,
    contentType: "text/event-stream",
    headers: { "cache-control": "no-cache" },
    body: events.map((e, i) => `id: ${i + 1}\ndata: ${JSON.stringify(e)}\n\n`).join(""),
  };
}

const ok = (json: unknown): Reply => ({ status: 200, json });
const noContent: Reply = { status: 204 };

export function defaultHandlers(): Record<string, Handler> {
  return {
    "GET /api/health": () => ok(fx.healthOk),
    "GET /api/auth/me": () => ok(fx.me),
    "POST /api/auth/login": () => ok(fx.me),
    "POST /api/auth/register": () => ok(fx.newUser),
    "POST /api/auth/logout": () => noContent,
    "GET /api/profile": () => ok(fx.profile),
    "PUT /api/profile": ({ body }) => ok({ ...fx.profile, ...(body as object) }),
    "GET /api/searches": () => ok(fx.searches),
    "POST /api/searches": ({ body }) => ok({ ...(body as object), search_id: "s_new" }),
    "DELETE /api/searches/:id": () => noContent,
    "GET /api/portfolio/items": () => ok(fx.portfolio),
    "POST /api/portfolio/upload": () => ok(fx.uploadResult),
    "GET /api/jobs": () => ok(fx.inbox),
    "POST /api/jobs/scout": () => ok({ ...fx.runStarted, run_id: "run_scout" }),
    "GET /api/jobs/:id": () => ok(fx.jobDetail),
    "POST /api/jobs/:id/analyze": () => ok(fx.runStarted),
    "POST /api/jobs/:id/skip": () => noContent,
    "GET /api/proposals/:id": () => ok(fx.studio),
    "POST /api/proposals/:id/regenerate": () => ok({ ...fx.runStarted, run_id: "run_regen" }),
    "POST /api/approvals/:id": ({ body }) => {
      const action = (body as { action: string }).action;
      return ok(fx.approvalResult(action === "reject" ? "rejected" : action === "edit" ? "rechecking" : "submitted"));
    },
    "GET /api/pipeline": () => ok(fx.pipeline),
    "GET /api/messages": () => ok(fx.conversations),
    "GET /api/messages/:id": () => ok(fx.conversation),
    "POST /api/messages/:id/draft": () => ok({ ...fx.runStarted, run_id: "run_reply" }),
    "GET /api/runs": () => ok(fx.runs),
    "GET /api/runs/:id": () => ok(fx.run),
    "GET /api/runs/:id/stream": () => sse(fx.runEvents),
    "GET /api/analytics": () => ok(fx.analytics),
    "GET /api/memory": () => ok(fx.memory),
    "DELETE /api/memory/:ns/:key": () => noContent,
    "POST /api/oauth/upwork/disconnect": () => noContent,
  };
}

function match(pattern: string, path: string): Record<string, string> | null {
  const p = pattern.split("/");
  const a = path.split("/");
  if (p.length !== a.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < p.length; i++) {
    if (p[i].startsWith(":")) params[p[i].slice(1)] = decodeURIComponent(a[i]);
    else if (p[i] !== a[i]) return null;
  }
  return params;
}

export async function mockApi(page: Page, overrides: Record<string, Handler> = {}) {
  const handlers = { ...defaultHandlers(), ...overrides };
  const calls: Recorded[] = [];
  // Exact routes first so "/api/jobs/scout" wins over "/api/jobs/:id".
  const entries = Object.entries(handlers).sort(
    ([a], [b]) => (a.includes(":") ? 1 : 0) - (b.includes(":") ? 1 : 0),
  );

  await page.route("**/api/**", async (route: Route) => {
    const req = route.request();
    const url = new URL(req.url());
    const method = req.method();
    const contentType = (await req.headerValue("content-type")) ?? null;
    let body: unknown = null;
    const raw = req.postData();
    if (raw && contentType?.includes("application/json")) body = JSON.parse(raw);
    else if (raw) body = raw;
    calls.push({ method, path: url.pathname, search: url.search, body, contentType });

    for (const [key, handler] of entries) {
      const [m, pattern] = key.split(" ");
      if (m !== method) continue;
      const params = match(pattern, url.pathname);
      if (!params) continue;
      const reply = (await handler({ req, params, url, body })) ?? { status: 204 };
      if (reply.json !== undefined) {
        return route.fulfill({ status: reply.status ?? 200, json: reply.json, headers: reply.headers });
      }
      return route.fulfill({
        status: reply.status ?? 200,
        body: reply.body ?? "",
        contentType: reply.contentType,
        headers: reply.headers,
      });
    }
    return route.fulfill({ status: 404, json: { detail: `not mocked: ${method} ${url.pathname}` } });
  });

  return {
    calls,
    /** Calls matching method and exact path. */
    find: (method: string, path: string) => calls.filter((c) => c.method === method && c.path === path),
    /** Replace or add a handler after setup. */
    set: (key: string, h: Handler) => {
      const i = entries.findIndex(([k]) => k === key);
      if (i >= 0) entries[i] = [key, h];
      else entries.unshift([key, h]);
    },
  };
}
