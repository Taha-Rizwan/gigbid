"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, PenLine, Radio, WifiOff } from "lucide-react";
import { keys, useRun } from "@/lib/hooks/queries";
import { useRunStream, type StreamState } from "@/lib/hooks/useRunStream";
import type { RunEvent, RunOut } from "@/lib/hooks/types";
import { buildLanes, RunEventLog, RunTimeline } from "@/components/RunTimeline";
import { Badge, Card, CardTitle, LinkButton, PageHeader, Stat, type Tone } from "@/components/ui";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { dateTime, humanize, seconds, usd } from "@/lib/format";

const TERMINAL = ["done", "failed", "needs_attention"];

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  return <RunViewer key={id} runId={id} />;
}

function RunViewer({ runId }: { runId: string }) {
  const qc = useQueryClient();
  const run = useRun(runId);
  const finished = !!run.data && TERMINAL.includes(run.data.status);
  // Stream unless the run had already finished when we loaded it.
  const { events: live, state } = useRunStream(runId, {
    enabled: !run.isPending && !finished,
    onEvent: (e) => {
      if (e.kind === "done" || e.kind === "interrupt" || e.kind === "error") {
        qc.invalidateQueries({ queryKey: keys.run(runId) });
      }
    },
  });

  const back = (
    <Link href="/runs" className="inline-flex items-center gap-1 text-muted hover:text-fg">
      <ArrowLeft aria-hidden className="size-4" /> Runs
    </Link>
  );

  if (run.isPending) return <LoadingState label="Connecting to the run" rows={3} />;
  if (run.isError)
    return (
      <>
        <PageHeader title="Agent run" back={back} />
        <ErrorState title="Could not load this run" error={run.error} onRetry={() => run.refetch()} />
      </>
    );

  const events = merge(run.data.events ?? [], live);
  return <RunView run={run.data} events={events} stream={finished ? "closed" : state} back={back} />;
}

function merge(a: RunEvent[], b: RunEvent[]): RunEvent[] {
  const m = new Map<number, RunEvent>();
  for (const e of [...a, ...b]) m.set(e.seq, e);
  return [...m.values()].sort((x, y) => x.seq - y.seq);
}

const STATUS_TONE: Record<RunOut["status"], Tone> = {
  queued: "neutral",
  running: "accent",
  interrupted: "amber",
  done: "green",
  failed: "red",
  needs_attention: "red",
};

function RunView({ run, events, stream, back }: { run: RunOut; events: RunEvent[]; stream: StreamState; back: ReactNode }) {
  const sawInterrupt = events.some((e) => e.kind === "interrupt");
  const sawDone = events.some((e) => e.kind === "done");
  // Live status: the stream can be ahead of the last GET.
  const status: RunOut["status"] =
    run.status === "running" || run.status === "queued"
      ? sawInterrupt
        ? "interrupted"
        : sawDone
          ? "done"
          : events.length
            ? "running"
            : run.status
      : run.status;
  const { lanes } = buildLanes(events);
  const tokens = Math.max(run.tokens, lanes.reduce((n, l) => n + (l.tokens ?? 0), 0));
  const cost = Math.max(run.cost_usd, lanes.reduce((n, l) => n + (l.cost ?? 0), 0));
  const firstAt = events[0]?.at ?? run.started_at;
  const lastAt = events.at(-1)?.at ?? run.finished_at;
  const latency =
    run.latency_s ??
    (firstAt && lastAt ? Math.max(0, (new Date(lastAt).getTime() - new Date(firstAt).getTime()) / 1000) : null);
  const studioHref = run.graph === "bid" ? `/studio/${run.thread_id}` : run.job_id ? `/jobs/${run.job_id}` : "/messages";

  return (
    <>
      <PageHeader
        back={back}
        title={`${run.graph === "bid" ? "Bid" : "Conversation"} run`}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone={STATUS_TONE[status]} data-testid="run-status" data-status={status}>
              {humanize(status)}
            </Badge>
            <span className="font-mono text-xs">{run.run_id}</span>
            {run.started_at && <span>· started {dateTime(run.started_at)}</span>}
            <StreamBadge state={stream} />
          </span>
        }
        actions={
          <>
            {status === "interrupted" && (
              <LinkButton href={studioHref} variant="primary" data-testid="open-studio">
                <PenLine aria-hidden className="size-4" /> Review in studio
              </LinkButton>
            )}
            {run.trace_url && (
              <a
                href={run.trace_url}
                target="_blank"
                rel="noreferrer"
                data-testid="trace-link"
                className="inline-flex items-center gap-1 text-sm text-accent underline"
              >
                Full trace <ExternalLink aria-hidden className="size-3.5" />
              </a>
            )}
          </>
        }
      />

      {status === "interrupted" && (
        <p className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/50 dark:text-amber-100">
          The graph paused for your approval. Nothing has been sent.
        </p>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Nodes" value={lanes.length} />
        <Stat label="Tokens" value={tokens.toLocaleString()} data-testid="run-tokens" />
        <Stat label="Cost" value={usd(cost)} data-testid="run-cost" />
        <Stat label="Latency" value={seconds(latency)} data-testid="run-latency" />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <Card>
            <CardTitle>Timeline</CardTitle>
            <RunTimeline events={events} />
          </Card>
        </div>
        <div className="lg:col-span-2">
          <Card>
            <CardTitle aside={<span className="text-xs text-muted">{events.length} events</span>}>Event log</CardTitle>
            {events.length === 0 ? (
              <p className="text-sm text-muted">Waiting for events…</p>
            ) : (
              <RunEventLog events={events} />
            )}
          </Card>
        </div>
      </div>
    </>
  );
}

function StreamBadge({ state }: { state: StreamState }) {
  if (state === "open" || state === "connecting")
    return (
      <span className="inline-flex items-center gap-1 text-xs text-accent" data-testid="stream-state" data-state={state}>
        <Radio aria-hidden className="size-3.5 animate-pulse" /> {state === "open" ? "Live" : "Connecting"}
      </span>
    );
  if (state === "reconnecting" || state === "error")
    return (
      <span className="inline-flex items-center gap-1 text-xs text-amber-700 dark:text-amber-300" data-testid="stream-state" data-state={state}>
        <WifiOff aria-hidden className="size-3.5" /> {state === "error" ? "Stream lost" : "Reconnecting"}
      </span>
    );
  return null;
}
