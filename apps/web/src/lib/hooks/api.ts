"use client";

import { client } from "@/lib/api/client";
import { markMarketplaceUnavailable } from "./degraded";

/** Error thrown by every hook when the API answers with a non-2xx status. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// A 401 from these is a form error (wrong password), not an expired session.
const AUTH_FORM_PATHS = ["/api/auth/login", "/api/auth/register"];

declare global {
  var __gigbidMiddleware: boolean | undefined;
}

if (typeof window !== "undefined" && !globalThis.__gigbidMiddleware) {
  globalThis.__gigbidMiddleware = true;
  client.use({
    onRequest({ request }) {
      // The session is an httpOnly cookie set by the backend; always send it.
      return new Request(request, { credentials: "include" });
    },
    async onResponse({ request, response }) {
      const path = new URL(request.url, window.location.origin).pathname;
      if (response.status === 401 && !AUTH_FORM_PATHS.includes(path)) {
        redirectToLogin();
      } else if (response.status === 503) {
        try {
          const body = await response.clone().json();
          if (body?.error === "marketplace_unavailable") {
            markMarketplaceUnavailable(body.detail, body.queued);
          }
        } catch {
          /* not JSON: ignore */
        }
      }
      return undefined;
    },
  });
}

function redirectToLogin() {
  const here = window.location.pathname + window.location.search;
  if (window.location.pathname.startsWith("/login")) return;
  // A full navigation on purpose: it drops all cached data of the expired session.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${encodeURIComponent(here)}`);
}

export const api = client;

function messageFrom(status: number, error: unknown): string {
  if (error && typeof error === "object") {
    const e = error as { detail?: unknown; error?: unknown };
    if (typeof e.detail === "string") return e.detail;
    if (Array.isArray(e.detail)) {
      // FastAPI 422: [{loc, msg, type}]
      return e.detail
        .map((d: { loc?: unknown[]; msg?: string }) =>
          [d.loc?.slice(1).join("."), d.msg].filter(Boolean).join(": "),
        )
        .join("; ");
    }
    if (typeof e.error === "string") return e.error.replaceAll("_", " ");
  }
  if (status === 401) return "You are signed out.";
  if (status === 404) return "Not found.";
  if (status === 503) return "Marketplace unavailable. Work is queued.";
  if (status >= 500) return "The GigBid API is not responding.";
  return `Request failed (${status}).`;
}

/** Turns an openapi-fetch result into data or a thrown ApiError. */
export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result: { data?: T; error?: unknown; response: Response };
  try {
    result = await promise;
  } catch (e) {
    throw new ApiError(0, "Network error: could not reach GigBid.", e);
  }
  const { data, error, response } = result;
  if (!response.ok) {
    throw new ApiError(response.status, messageFrom(response.status, error), error);
  }
  return data as T;
}

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "Something went wrong.";
}
