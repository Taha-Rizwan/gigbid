import { AlertOctagon, CheckCircle2, CirclePause, Loader2 } from "lucide-react";
import type { RunEvent } from "@/lib/hooks/types";
import { clock, cx, humanize, seconds, usd } from "@/lib/format";

type NodeState = "running" | "done" | "error" | "interrupted";

export interface NodeLane {
  node: string;
  start: number;
  end: number | null;
  state: NodeState;
  summary: string;
  tokens?: number;
  cost?: number;
  latency?: number;
  model?: string;
  parallelWith: string[];
}

const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : undefined);

/** Folds the event stream into one lane per graph node. */
export function buildLanes(events: RunEvent[]): { lanes: NodeLane[]; t0: number; t1: number } {
  const byNode = new Map<string, NodeLane>();
  let t0 = Infinity;
  let t1 = -Infinity;
  for (const ev of events) {
    const t = new Date(ev.at).getTime();
    if (Number.isFinite(t)) {
      t0 = Math.min(t0, t);
      t1 = Math.max(t1, t);
    }
    if (ev.kind === "done") continue;
    let lane = byNode.get(ev.node);
    if (!lane) {
      lane = { node: ev.node, start: t, end: null, state: "running", summary: "", parallelWith: [] };
      byNode.set(ev.node, lane);
    }
    if (ev.summary) lane.summary = ev.summary;
    const d = ev.data ?? {};
    lane.tokens = num(d.tokens) ?? num(d.total_tokens) ?? lane.tokens;
    lane.cost = num(d.cost_usd) ?? lane.cost;
    lane.latency = num(d.latency_s) ?? (num(d.latency_ms) !== undefined ? num(d.latency_ms)! / 1000 : lane.latency);
    if (typeof d.model === "string") lane.model = d.model;
    if (ev.kind === "end") {
      lane.end = t;
      lane.state = lane.state === "error" ? "error" : "done";
    } else if (ev.kind === "error") {
      lane.end = t;
      lane.state = "error";
    } else if (ev.kind === "interrupt") {
      lane.end = t;
      lane.state = "interrupted";
    }
  }
  if (!Number.isFinite(t0)) {
    t0 = 0;
    t1 = 1;
  }
  const lanes = [...byNode.values()].sort((a, b) => a.start - b.start);
  for (const a of lanes) {
    const aEnd = a.end ?? t1;
    a.parallelWith = lanes
      .filter((b) => b !== a && b.start < aEnd && a.start < (b.end ?? t1))
      .map((b) => b.node);
  }
  return { lanes, t0, t1 };
}

const STATE_UI: Record<NodeState, { bar: string; Icon: typeof CheckCircle2; label: string; spin?: boolean }> = {
  running: { bar: "bg-accent/70 animate-pulse", Icon: Loader2, label: "Running", spin: true },
  done: { bar: "bg-emerald-500/80", Icon: CheckCircle2, label: "Done" },
  error: { bar: "bg-red-500/80", Icon: AlertOctagon, label: "Error" },
  interrupted: { bar: "bg-amber-500/80", Icon: CirclePause, label: "Waiting for you" },
};

/**
 * Node-by-node timeline. Each lane is placed on a shared time axis, so the
 * agents that run in parallel (job analyst, risk assessor, fit matcher) are
 * visibly side by side.
 */
export function RunTimeline({ events }: { events: RunEvent[] }) {
  const { lanes, t0, t1 } = buildLanes(events);
  const span = Math.max(1, t1 - t0);

  if (lanes.length === 0) {
    return (
      <div role="status" className="flex items-center gap-2 rounded-lg border border-dashed border-line p-4 text-sm text-muted">
        <Loader2 aria-hidden className="size-4 animate-spin" /> Waiting for the first node to start…
      </div>
    );
  }

  return (
    <ol className="space-y-2" data-testid="run-timeline" aria-label="Graph nodes">
      {lanes.map((l) => {
        const ui = STATE_UI[l.state];
        const left = ((l.start - t0) / span) * 100;
        const width = Math.max(1.5, (((l.end ?? t1) - l.start) / span) * 100);
        return (
          <li
            key={l.node}
            data-testid="timeline-node"
            data-node={l.node}
            data-state={l.state}
            className="rounded-lg border border-line bg-surface p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
              <div className="flex min-w-0 items-center gap-2">
                <ui.Icon
                  aria-hidden
                  className={cx(
                    "size-4 shrink-0",
                    ui.spin && "animate-spin",
                    l.state === "done" && "text-emerald-600 dark:text-emerald-400",
                    l.state === "error" && "text-red-600 dark:text-red-400",
                    l.state === "interrupted" && "text-amber-600 dark:text-amber-400",
                    l.state === "running" && "text-accent",
                  )}
                />
                <span className="font-medium">{humanize(l.node)}</span>
                <span className="sr-only">{ui.label}</span>
                {l.parallelWith.length > 0 && (
                  <span className="rounded bg-accent-soft px-1.5 py-0.5 text-[11px] font-medium text-accent">
                    parallel
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-x-3 text-xs text-muted tabular-nums">
                {l.tokens !== undefined && <span>{l.tokens.toLocaleString()} tok</span>}
                {l.cost !== undefined && <span>{usd(l.cost)}</span>}
                <span>
                  {l.latency !== undefined
                    ? seconds(l.latency)
                    : l.end !== null
                      ? seconds((l.end - l.start) / 1000)
                      : ui.label}
                </span>
              </div>
            </div>
            <div className="relative mt-2 h-2 rounded-full bg-subtle" aria-hidden>
              <div
                className={cx("absolute inset-y-0 rounded-full", ui.bar)}
                style={{ left: `${left}%`, width: `${Math.min(width, 100 - left)}%` }}
              />
            </div>
            {l.summary && <p className="mt-2 text-sm text-muted">{l.summary}</p>}
          </li>
        );
      })}
    </ol>
  );
}

/** Raw event log, appended as events arrive. */
export function RunEventLog({ events }: { events: RunEvent[] }) {
  return (
    <ol aria-live="polite" aria-label="Run events" data-testid="run-event-log" className="divide-y divide-line text-sm">
      {events.map((e) => (
        <li key={e.seq} className="grid grid-cols-[3.5rem_minmax(0,1fr)] gap-x-3 py-2 sm:grid-cols-[4.5rem_10rem_minmax(0,1fr)]">
          <span className="font-mono text-xs text-muted tabular-nums">{clock(e.at)}</span>
          <span className="truncate font-medium">
            {humanize(e.node)} <span className="font-normal text-muted">· {e.kind}</span>
          </span>
          <span className="col-span-2 text-muted sm:col-span-1">{e.summary}</span>
        </li>
      ))}
    </ol>
  );
}
