"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ApiError } from "@/lib/hooks/api";

function shouldRetry(count: number, err: unknown) {
  if (count >= 2) return false;
  if (!(err instanceof ApiError)) return true;
  // Retry network errors and 5xx, but not 4xx and not "marketplace unavailable".
  return err.status === 0 || (err.status >= 500 && err.status !== 503);
}

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 10_000, retry: shouldRetry },
    },
  });
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeClient);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
