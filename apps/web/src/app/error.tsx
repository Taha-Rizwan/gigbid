"use client";

import { ErrorState } from "@/components/ErrorState";

export default function RouteError({ error, reset }: { error: Error; reset: () => void }) {
  return <ErrorState title="This page crashed" error={error} onRetry={reset} />;
}
