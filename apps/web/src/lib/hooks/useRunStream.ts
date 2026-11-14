"use client";

import { useEffect, useRef, useState } from "react";
import type { RunEvent } from "./types";

export type StreamState = "connecting" | "open" | "reconnecting" | "closed" | "error";

/**
 * Subscribes to `GET /api/runs/{id}/stream` (Server-Sent Events). Every `data:`
 * frame is one RunEvent; the stream ends with an event of kind `done`.
 * EventSource reconnects on its own and sends Last-Event-ID, so events are
 * de-duplicated by `seq`.
 *
 * Mount this under a component keyed by `runId` so state resets per run.
 */
export function useRunStream(
  runId: string,
  opts: { enabled?: boolean; onEvent?: (e: RunEvent) => void } = {},
) {
  const { enabled = true } = opts;
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [state, setState] = useState<StreamState>(enabled ? "connecting" : "closed");
  const onEventRef = useRef(opts.onEvent);

  useEffect(() => {
    onEventRef.current = opts.onEvent;
  });

  useEffect(() => {
    if (!enabled) return;
    const es = new EventSource(`/api/runs/${encodeURIComponent(runId)}/stream`, {
      withCredentials: true,
    });
    es.onopen = () => setState("open");
    es.onmessage = (msg) => {
      let ev: RunEvent;
      try {
        ev = JSON.parse(msg.data) as RunEvent;
      } catch {
        return;
      }
      setEvents((prev) =>
        prev.some((p) => p.seq === ev.seq) ? prev : [...prev, ev].sort((a, b) => a.seq - b.seq),
      );
      onEventRef.current?.(ev);
      if (ev.kind === "done") {
        es.close();
        setState("closed");
      }
    };
    es.onerror = () => {
      setState(es.readyState === EventSource.CLOSED ? "error" : "reconnecting");
    };
    return () => es.close();
  }, [runId, enabled]);

  return { events, state };
}
