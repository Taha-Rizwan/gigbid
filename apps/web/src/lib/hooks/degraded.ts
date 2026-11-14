"use client";

import { useSyncExternalStore } from "react";

/**
 * Tiny global store: set when any request returns 503 `marketplace_unavailable`,
 * cleared once /api/health reports `ok` again after that moment.
 */
type State = { since: number | null; detail: string | null; queued: number };

let state: State = { since: null, detail: null, queued: 0 };
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

export function markMarketplaceUnavailable(detail?: string, queued?: number) {
  state = { since: Date.now(), detail: detail ?? null, queued: queued ?? 0 };
  emit();
}

export function clearMarketplaceUnavailable(healthyAt: number) {
  if (state.since !== null && healthyAt > state.since) {
    state = { since: null, detail: null, queued: 0 };
    emit();
  }
}

const SERVER_STATE: State = { since: null, detail: null, queued: 0 };

export function useMarketplaceUnavailable(): State {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
    () => SERVER_STATE,
  );
}
