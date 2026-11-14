import { Loader2 } from "lucide-react";

/** Skeleton rows plus a screen-reader status, so loading is never a bare spinner. */
export function LoadingState({ label = "Loading", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div data-testid="loading-state" role="status" aria-live="polite" className="space-y-3">
      <div className="flex items-center gap-2 text-sm text-muted">
        <Loader2 aria-hidden className="size-4 animate-spin" />
        <span>{label}…</span>
      </div>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-lg border border-line bg-surface" />
      ))}
    </div>
  );
}
