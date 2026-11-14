/**
 * GENERATED FILE - DO NOT HAND-EDIT.
 * Typed client for the GigBid API, bound to the types in ./schema.d.ts
 * (regenerate those with `npm run gen:api`). Same-origin: Next.js rewrites
 * /api/* to the FastAPI backend. Request middleware (cookies, 401, 503) is
 * registered in src/lib/hooks/api.ts, not here.
 */
import createClient from "openapi-fetch";
import type { paths } from "./schema";

export const client = createClient<paths>({ baseUrl: "" });
