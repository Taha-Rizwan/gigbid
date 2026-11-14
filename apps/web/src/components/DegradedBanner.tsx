"use client";

import { useEffect } from "react";
import { CloudOff } from "lucide-react";
import { useHealth } from "@/lib/hooks/queries";
import { clearMarketplaceUnavailable, useMarketplaceUnavailable } from "@/lib/hooks/degraded";

/**
 * Global banner. Polls GET /api/health every 20 s and also reacts to any
 * request that returned 503 `marketplace_unavailable`.
 */
export function DegradedBanner() {
  const health = useHealth();
  const flagged = useMarketplaceUnavailable();
  const { data, dataUpdatedAt } = health;

  useEffect(() => {
    if (data?.status === "ok") clearMarketplaceUnavailable(dataUpdatedAt);
  }, [data?.status, dataUpdatedAt]);

  const healthBad = !!data && data.status !== "ok";
  if (!healthBad && flagged.since === null) return null;

  const queued = Math.max(data?.queued_while_degraded ?? 0, flagged.queued);
  const bad = data?.services.filter((s) => s.status !== "ok") ?? [];

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="degraded-banner"
      className="border-b border-amber-300 bg-amber-50 px-4 py-2.5 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/70 dark:text-amber-100"
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-3 gap-y-1">
        <CloudOff aria-hidden className="size-4 shrink-0" />
        <p className="font-medium">
          Marketplace unavailable: work is queued and will resume automatically
        </p>
        {queued > 0 && <span className="opacity-80">({queued} queued)</span>}
        {bad.length > 0 && (
          <span className="opacity-80">
            Affected: {bad.map((s) => `${s.name} (${s.status})`).join(", ")}
          </span>
        )}
      </div>
    </div>
  );
}
