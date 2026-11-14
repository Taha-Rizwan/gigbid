"use client";

import Link from "next/link";
import { Activity } from "lucide-react";
import { useRuns } from "@/lib/hooks/queries";
import { dateTime, humanize, seconds, usd } from "@/lib/format";
import { Badge, PageHeader } from "@/components/ui";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";

export default function RunsPage() {
  const runs = useRuns();
  return (
    <>
      <PageHeader title="Agent runs" description="Every graph run, newest first. Open one to watch it node by node." />
      {runs.isPending ? (
        <LoadingState label="Loading runs" />
      ) : runs.isError ? (
        <ErrorState error={runs.error} onRetry={() => runs.refetch()} />
      ) : runs.data.length === 0 ? (
        <EmptyState icon={<Activity className="size-8" />} title="No runs yet" description="Analyze a job or scout for jobs to start one." />
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface" data-testid="run-list">
          {runs.data.map((r) => (
            <li key={r.run_id}>
              <Link href={`/runs/${r.run_id}`} className="flex flex-col gap-1 px-4 py-3 hover:bg-subtle sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-center gap-2">
                  <Badge tone={r.status === "done" ? "green" : r.status === "interrupted" ? "amber" : r.status === "failed" || r.status === "needs_attention" ? "red" : "accent"}>
                    {humanize(r.status)}
                  </Badge>
                  <span className="font-medium">{r.graph === "bid" ? "Bid graph" : "Conversation graph"}</span>
                  <span className="truncate font-mono text-xs text-muted">{r.run_id}</span>
                </div>
                <div className="flex flex-wrap gap-x-4 text-xs text-muted tabular-nums">
                  <span>{r.tokens.toLocaleString()} tok</span>
                  <span>{usd(r.cost_usd)}</span>
                  <span>{seconds(r.latency_s)}</span>
                  <span>{dateTime(r.started_at)}</span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
