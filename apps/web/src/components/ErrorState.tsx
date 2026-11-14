"use client";

import { AlertTriangle } from "lucide-react";
import { ApiError, errorMessage } from "@/lib/hooks/api";
import { Button } from "./ui";

export function ErrorState({
  error,
  title = "Could not load this",
  onRetry,
}: {
  error: unknown;
  title?: string;
  onRetry?: () => void;
}) {
  const status = error instanceof ApiError ? error.status : undefined;
  return (
    <div
      data-testid="error-state"
      role="alert"
      className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle aria-hidden className="mt-0.5 size-5 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">
            {title}
            {status ? <span className="font-normal opacity-80"> (HTTP {status})</span> : null}
          </p>
          <p className="mt-1">{errorMessage(error)}</p>
          {onRetry && (
            <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
              Try again
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

/** Inline mutation error, used under forms and action buttons. */
export function InlineError({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="text-sm text-red-700 dark:text-red-300">
      {errorMessage(error)}
    </p>
  );
}
