"use client";

import Link from "next/link";
import { useDeferredValue, useState, type FormEvent } from "react";
import { Coins, PenLine, Radar, Search, X } from "lucide-react";
import { useInbox, useScout, useSkip, type InboxFilters } from "@/lib/hooks/queries";
import type { InboxItem, JobStatus, Recommendation } from "@/lib/hooks/types";
import { JOB_STATUSES } from "@/lib/hooks/types";
import { dateTime, humanize, price } from "@/lib/format";
import { Badge, Button, Input, LinkButton, Meter, PageHeader, Select } from "@/components/ui";
import { RecommendationBadge, RiskBadge } from "@/components/RiskBadge";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState, InlineError } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";

export default function InboxPage() {
  const [recommendation, setRecommendation] = useState<Recommendation | "">("");
  const [status, setStatus] = useState<JobStatus | "">("");
  const [q, setQ] = useState("");
  const deferredQ = useDeferredValue(q);
  const filters: InboxFilters = {
    recommendation: recommendation || undefined,
    status: status || undefined,
    q: deferredQ.trim() || undefined,
    sort: "fit",
  };
  const inbox = useInbox(filters);
  const scout = useScout();

  return (
    <>
      <PageHeader
        title="Job inbox"
        description="New jobs ranked by fit. Risk and price are assessed by the agents before you see them."
        actions={
          <Button data-testid="scout-now" onClick={() => scout.mutate()} loading={scout.isPending}>
            <Radar aria-hidden className="size-4" /> Scout now
          </Button>
        }
      />

      {scout.data && (
        <p role="status" data-testid="scout-started" className="mb-4 rounded-md bg-accent-soft px-3 py-2 text-sm">
          Scouting started.{" "}
          <Link className="font-medium text-accent underline" href={`/runs/${scout.data.run_id}`}>
            Watch the run live
          </Link>
        </p>
      )}
      {scout.isError && (
        <div className="mb-4">
          <InlineError error={scout.error} />
        </div>
      )}

      <div className="mb-4 grid gap-2 sm:grid-cols-[minmax(0,1fr)_11rem_12rem]" role="search">
        <label className="relative block">
          <span className="sr-only">Search jobs</span>
          <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input
            data-testid="inbox-search"
            type="search"
            placeholder="Search title, skills, client…"
            className="pl-9"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
        <label>
          <span className="sr-only">Recommendation</span>
          <Select
            data-testid="filter-recommendation"
            value={recommendation}
            onChange={(e) => setRecommendation(e.target.value as Recommendation | "")}
          >
            <option value="">Any action</option>
            <option value="bid">Bid</option>
            <option value="watch">Watch</option>
            <option value="skip">Skip</option>
          </Select>
        </label>
        <label>
          <span className="sr-only">Status</span>
          <Select data-testid="filter-status" value={status} onChange={(e) => setStatus(e.target.value as JobStatus | "")}>
            <option value="">All statuses</option>
            {JOB_STATUSES.map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </Select>
        </label>
      </div>

      {inbox.isPending ? (
        <LoadingState label="Loading jobs" />
      ) : inbox.isError ? (
        <ErrorState title="Could not load the inbox" error={inbox.error} onRetry={() => inbox.refetch()} />
      ) : inbox.data.items.length === 0 ? (
        <EmptyState
          title={filters.q || filters.status || filters.recommendation ? "No jobs match these filters" : "No jobs yet"}
          description="Run the scout to pull new jobs from your saved searches."
          action={
            <Button onClick={() => scout.mutate()} loading={scout.isPending}>
              <Radar aria-hidden className="size-4" /> Scout now
            </Button>
          }
        />
      ) : (
        <>
          <p className="mb-2 text-xs text-muted" aria-live="polite">
            Showing {inbox.data.items.length} of {inbox.data.total} jobs{inbox.isFetching ? " · refreshing…" : ""}
          </p>
          <ul className="space-y-3" data-testid="inbox-list">
            {inbox.data.items.map((job) => (
              <JobRow key={job.job_id} job={job} />
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function JobRow({ job }: { job: InboxItem }) {
  const skip = useSkip();
  const [skipping, setSkipping] = useState(false);
  const [reason, setReason] = useState("");
  const fit = job.fit_score ?? null;
  const reviewable = job.thread_id && job.status === "awaiting_approval";

  const submitSkip = (e: FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) return;
    skip.mutate({ jobId: job.job_id, reason: reason.trim() }, { onSuccess: () => setSkipping(false) });
  };

  return (
    <li data-testid="job-row" data-job-id={job.job_id} className="rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <RecommendationBadge value={job.recommendation} />
            <RiskBadge level={job.risk_level} score={job.risk_score} flags={job.risk_flags} />
            {job.status !== "new" && <Badge>{humanize(job.status)}</Badge>}
            {job.category && <span className="text-xs text-muted">{job.category}</span>}
          </div>
          <h2 className="mt-2 font-semibold">
            <Link href={`/jobs/${job.job_id}`} className="hover:underline">
              {job.title}
            </Link>
          </h2>
          <p className="mt-1 line-clamp-2 text-sm text-muted">{job.snippet}</p>
          {(job.risk_flags?.length ?? 0) > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Risk flags">
              {job.risk_flags!.map((f) => (
                <li key={f}>
                  <Badge tone="red">{humanize(f)}</Badge>
                </li>
              ))}
            </ul>
          )}
        </div>

        <dl className="grid shrink-0 grid-cols-3 gap-3 text-sm md:w-72">
          <div>
            <dt className="text-xs text-muted">Fit</dt>
            <dd className="font-semibold tabular-nums">{fit === null ? "—" : Math.round(fit * 100)}</dd>
            {fit !== null && <Meter value={fit} label="Fit score" tone={fit >= 0.7 ? "green" : fit >= 0.4 ? "amber" : "red"} />}
          </div>
          <div>
            <dt className="text-xs text-muted">Price</dt>
            <dd className="font-semibold tabular-nums">{price(job.price, job.rate_type)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted">Connects</dt>
            <dd className="flex items-center gap-1 font-semibold tabular-nums">
              <Coins aria-hidden className="size-3.5 text-muted" />
              {job.connects_cost ?? "—"}
            </dd>
          </div>
        </dl>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
        <LinkButton href={`/jobs/${job.job_id}`} size="sm" variant="secondary" data-testid="open-job">
          Open
        </LinkButton>
        {reviewable && (
          <LinkButton href={`/studio/${job.thread_id}`} size="sm" variant="primary" data-testid="review-draft">
            <PenLine aria-hidden className="size-3.5" /> Review draft
          </LinkButton>
        )}
        {job.status !== "skipped" && !skipping && (
          <Button size="sm" variant="ghost" data-testid="skip-job" onClick={() => setSkipping(true)}>
            Skip…
          </Button>
        )}
        {job.posted_at && <span className="ml-auto text-xs text-muted">Posted {dateTime(job.posted_at)}</span>}
      </div>

      {skipping && (
        <form onSubmit={submitSkip} className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
          <label htmlFor={`skip-${job.job_id}`} className="sr-only">
            Reason for skipping
          </label>
          <Input
            id={`skip-${job.job_id}`}
            data-testid="skip-reason"
            autoFocus
            required
            maxLength={500}
            placeholder="Why skip? e.g. budget too low"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" variant="danger" data-testid="confirm-skip" loading={skip.isPending} disabled={!reason.trim()}>
              Skip job
            </Button>
            <Button size="sm" variant="ghost" aria-label="Cancel skip" onClick={() => setSkipping(false)}>
              <X aria-hidden className="size-4" />
            </Button>
          </div>
          <InlineError error={skip.error} />
        </form>
      )}
    </li>
  );
}
