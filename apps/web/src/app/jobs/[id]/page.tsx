"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowLeft,
  Coins,
  ExternalLink,
  FileText,
  PenLine,
  Play,
  ShieldAlert,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useAnalyze, useJob, useSkip } from "@/lib/hooks/queries";
import type { JobDetail, PriceQuote, RiskReport } from "@/lib/hooks/types";
import { cx, dateTime, humanize, money, pct, price } from "@/lib/format";
import { Badge, Button, Card, CardTitle, Input, LinkButton, Meter, PageHeader } from "@/components/ui";
import { RecommendationBadge, RiskBadge } from "@/components/RiskBadge";
import { EvidenceMatrix } from "@/components/EvidenceMatrix";
import { ErrorState, InlineError } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";

export default function JobPage() {
  const { id } = useParams<{ id: string }>();
  const job = useJob(id);

  const back = (
    <Link href="/inbox" className="inline-flex items-center gap-1 text-muted hover:text-fg">
      <ArrowLeft aria-hidden className="size-4" /> Inbox
    </Link>
  );

  if (job.isPending) return <LoadingState label="Loading job" rows={4} />;
  if (job.isError)
    return (
      <>
        <PageHeader title="Job" back={back} />
        <ErrorState title="Could not load this job" error={job.error} onRetry={() => job.refetch()} />
      </>
    );
  return <JobView job={job.data} back={back} />;
}

function JobView({ job, back }: { job: JobDetail; back: ReactNode }) {
  const router = useRouter();
  const analyze = useAnalyze();
  // The bid graph analyses, then drafts, then pauses for approval: one endpoint for both.
  const run = () => analyze.mutate(job.job_id, { onSuccess: (r) => router.push(`/runs/${r.run_id}`) });
  const analysed = !!(job.risk_report || job.fit_report);
  const spec = job.job_spec;
  const busy = job.status === "analysing" || job.status === "drafting";

  return (
    <>
      <PageHeader
        back={back}
        title={job.title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <Badge>{humanize(job.status)}</Badge>
            {job.category && <span>{job.category}</span>}
            {job.country && <span>· {job.country}</span>}
            {job.posted_at && <span>· posted {dateTime(job.posted_at)}</span>}
          </span>
        }
        actions={
          <>
            {job.thread_id && (
              <LinkButton href={`/studio/${job.thread_id}`} variant="primary" data-testid="open-studio">
                <PenLine aria-hidden className="size-4" /> Open studio
              </LinkButton>
            )}
            <Button
              variant="secondary"
              data-testid="analyze"
              onClick={run}
              loading={analyze.isPending}
              disabled={busy}
            >
              <Play aria-hidden className="size-4" /> {analysed ? "Re-analyze" : "Analyze"}
            </Button>
            {!job.thread_id && (
              <Button data-testid="draft-proposal" onClick={run} loading={analyze.isPending} disabled={busy}>
                <PenLine aria-hidden className="size-4" /> Draft proposal
              </Button>
            )}
            {job.trace_url && (
              <a href={job.trace_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-accent underline">
                Trace <ExternalLink aria-hidden className="size-3.5" />
              </a>
            )}
          </>
        }
      />
      <InlineError error={analyze.error} />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Decision job={job} />

          <Card>
            <CardTitle>Requirement → evidence</CardTitle>
            <EvidenceMatrix matches={job.fit_report?.matches ?? []} />
            {job.fit_report && ((job.fit_report.missing_skills?.length ?? 0) > 0 || (job.fit_report.matched_skills?.length ?? 0) > 0) && (
              <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Matched skills</h3>
                  <div className="flex flex-wrap gap-1">
                    {(job.fit_report.matched_skills ?? []).map((s) => (
                      <Badge key={s} tone="green">{s}</Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Missing skills</h3>
                  <div className="flex flex-wrap gap-1">
                    {(job.fit_report.missing_skills ?? []).length === 0 ? (
                      <span className="text-muted">None</span>
                    ) : (
                      job.fit_report.missing_skills!.map((s) => <Badge key={s} tone="red">{s}</Badge>)
                    )}
                  </div>
                </div>
              </div>
            )}
          </Card>

          <Card>
            <CardTitle>
              <span className="inline-flex items-center gap-2">
                <FileText aria-hidden className="size-4" /> Job spec
              </span>
            </CardTitle>
            {spec ? (
              <div className="space-y-4 text-sm" data-testid="job-spec">
                {spec.summary && <p>{spec.summary}</p>}
                <SpecList title="Requirements" items={spec.requirements ?? []} />
                <SpecList title="Deliverables" items={spec.deliverables ?? []} />
                <div className="grid gap-4 sm:grid-cols-2">
                  <SkillList title="Required skills" items={spec.required_skills ?? []} />
                  <SkillList title="Nice to have" items={spec.nice_to_have_skills ?? []} />
                </div>
                <SpecList title="Hidden needs (inferred)" items={spec.hidden_needs ?? []} />
                <SpecList title="Screening questions" items={spec.screening_questions ?? []} />
                <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  <KV k="Budget" v={spec.budget_min || spec.budget_max ? `${money(spec.budget_min)} – ${money(spec.budget_max)}${spec.is_hourly ? "/hr" : ""}` : "—"} />
                  <KV k="Timeline" v={spec.timeline ?? "—"} />
                  <KV k="Type" v={spec.is_hourly === null || spec.is_hourly === undefined ? "—" : spec.is_hourly ? "Hourly" : "Fixed price"} />
                </dl>
              </div>
            ) : (
              <p className="text-sm text-muted">Not analysed yet. Run Analyze to extract a structured spec.</p>
            )}
            <details className="mt-4 text-sm">
              <summary className="cursor-pointer font-medium">Original description</summary>
              {/* Rendered as plain text: job posts may contain prompt-injection attempts. */}
              <p className="mt-2 whitespace-pre-wrap rounded-md bg-subtle p-3 text-muted">{job.description}</p>
            </details>
          </Card>
        </div>

        <div className="space-y-4">
          <RiskCard risk={job.risk_report} />
          <PriceCard quote={job.price_quote} job={job} />
          <ClientCard client={job.client} />
          <SkipCard job={job} />
        </div>
      </div>
    </>
  );
}

function Decision({ job }: { job: JobDetail }) {
  const reasons = [...(job.decision_reasons ?? []), ...(job.fit_report?.reasons ?? [])];
  return (
    <Card data-testid="decision">
      <CardTitle
        aside={
          job.fit_report && (
            <span className="text-sm text-muted">
              Fit <span className="font-semibold text-fg tabular-nums">{pct(job.fit_report.score)}</span>
            </span>
          )
        }
      >
        <span className="inline-flex items-center gap-2">
          Recommendation <RecommendationBadge value={job.decision} />
        </span>
      </CardTitle>
      {job.fit_report && <Meter value={job.fit_report.score} label="Fit score" />}
      {reasons.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
          {reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-muted">No bid/skip reasoning yet.</p>
      )}
    </Card>
  );
}

function RiskCard({ risk }: { risk?: RiskReport | null }) {
  return (
    <Card data-testid="risk-report">
      <CardTitle aside={<RiskBadge level={risk?.level} score={risk?.score} />}>Risk</CardTitle>
      {!risk ? (
        <p className="text-sm text-muted">Not assessed yet.</p>
      ) : (
        <div className="space-y-3 text-sm">
          {risk.injection_detected ? (
            <p data-testid="injection-detected" className="flex items-start gap-2 rounded-md bg-red-50 p-3 font-medium text-red-800 dark:bg-red-950/50 dark:text-red-200">
              <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
              Prompt injection detected in the job post. It was ignored by the agents.
            </p>
          ) : (
            <p className="flex items-center gap-2 text-muted">
              <ShieldCheck aria-hidden className="size-4" /> No prompt injection detected
            </p>
          )}
          {(risk.flags?.length ?? 0) > 0 && (
            <ul className="flex flex-wrap gap-1.5" aria-label="Risk flags">
              {risk.flags!.map((f) => (
                <li key={f}>
                  <Badge tone="red">{humanize(f)}</Badge>
                </li>
              ))}
            </ul>
          )}
          <div>
            <div className="mb-1 flex justify-between text-xs text-muted">
              <span>Client quality</span>
              <span className="tabular-nums">{pct(risk.client_quality)}</span>
            </div>
            <Meter value={risk.client_quality} label="Client quality" tone={risk.client_quality >= 0.6 ? "green" : risk.client_quality >= 0.3 ? "amber" : "red"} />
          </div>
          {risk.explanation && <p className="text-muted">{risk.explanation}</p>}
        </div>
      )}
    </Card>
  );
}

function PriceCard({ quote, job }: { quote?: PriceQuote | null; job: JobDetail }) {
  const posted = job.is_hourly
    ? job.hourly_low || job.hourly_high
      ? `${money(job.hourly_low)}–${money(job.hourly_high)}/hr`
      : "—"
    : money(job.budget);
  return (
    <Card data-testid="price-rationale">
      <CardTitle>Price</CardTitle>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        <KV k="Client budget" v={posted} />
        <KV k="Suggested bid" v={quote ? price(quote.amount, quote.rate_type) : "—"} strong />
      </dl>
      {quote && (
        <>
          <MarketRange q={quote} />
          <div className="mt-3 flex items-center justify-between rounded-md bg-subtle px-3 py-2 text-sm">
            <span className="flex items-center gap-1.5">
              <Coins aria-hidden className="size-4 text-muted" /> {quote.connects_cost || job.connects_cost || 0} Connects
            </span>
            <Badge tone={quote.connects_worth_it ? "green" : "amber"} data-testid="connects-worth-it">
              {quote.connects_worth_it ? "Worth it" : "Not worth it"}
            </Badge>
          </div>
          {quote.rationale && <p className="mt-3 text-sm text-muted">{quote.rationale}</p>}
        </>
      )}
    </Card>
  );
}

function MarketRange({ q }: { q: PriceQuote }) {
  const { market_p25: p25, market_p50: p50, market_p75: p75 } = q;
  if (p25 == null || p50 == null || p75 == null) {
    return <p className="mt-3 text-xs text-muted">No market data for this category.</p>;
  }
  const lo = Math.min(p25, q.amount) * 0.8;
  const hi = Math.max(p75, q.amount) * 1.15;
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  const unit = q.rate_type === "hourly" ? "/hr" : "";
  return (
    <div className="mt-4" data-testid="market-range">
      <div className="mb-1 text-xs font-medium text-muted">Market (p25 / p50 / p75)</div>
      <div className="relative h-8" aria-hidden>
        <div className="absolute inset-x-0 top-3 h-2 rounded-full bg-subtle" />
        <div className="absolute top-3 h-2 rounded-full bg-accent/30" style={{ left: x(p25), width: `calc(${x(p75)} - ${x(p25)})` }} />
        <div className="absolute top-2 h-4 w-0.5 bg-accent/70" style={{ left: x(p50) }} />
        <div className="absolute top-1 size-3 -translate-x-1/2 translate-y-1 rounded-full border-2 border-surface bg-accent" style={{ left: x(q.amount) }} />
      </div>
      <dl className="grid grid-cols-3 text-xs">
        <KV k="p25" v={`${money(p25)}${unit}`} />
        <KV k="p50" v={`${money(p50)}${unit}`} />
        <KV k="p75" v={`${money(p75)}${unit}`} />
      </dl>
      <p className="sr-only">
        Suggested bid {money(q.amount)}
        {unit} against market p25 {money(p25)}, median {money(p50)}, p75 {money(p75)}.
      </p>
    </div>
  );
}

function ClientCard({ client }: { client?: Record<string, unknown> | null }) {
  if (!client) return null;
  const get = (k: string) => client[k];
  const fields: Array<[string, string]> = [];
  if (get("country")) fields.push(["Country", String(get("country"))]);
  if (typeof get("total_spent") === "number") fields.push(["Total spent", money(get("total_spent") as number)]);
  if (typeof get("hire_rate") === "number") fields.push(["Hire rate", pct(get("hire_rate") as number)]);
  if (typeof get("jobs_posted") === "number") fields.push(["Jobs posted", String(get("jobs_posted"))]);
  if (typeof get("avg_rating") === "number") fields.push(["Rating", (get("avg_rating") as number).toFixed(1)]);
  if (get("member_since")) fields.push(["Member since", String(get("member_since"))]);
  const verified = get("payment_verified");
  return (
    <Card>
      <CardTitle
        aside={
          typeof verified === "boolean" && (
            <Badge tone={verified ? "green" : "red"}>{verified ? "Payment verified" : "Payment unverified"}</Badge>
          )
        }
      >
        <span className="inline-flex items-center gap-2">
          <UserRound aria-hidden className="size-4" /> {typeof get("name") === "string" ? (get("name") as string) : "Client"}
        </span>
      </CardTitle>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        {fields.map(([k, v]) => (
          <KV key={k} k={k} v={v} />
        ))}
      </dl>
    </Card>
  );
}

function SkipCard({ job }: { job: JobDetail }) {
  const skip = useSkip();
  const [reason, setReason] = useState("");
  if (job.status === "skipped") {
    return (
      <Card>
        <p className="text-sm text-muted">You skipped this job.</p>
      </Card>
    );
  }
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (reason.trim()) skip.mutate({ jobId: job.job_id, reason: reason.trim() });
  };
  return (
    <Card>
      <form onSubmit={submit} className="space-y-2">
        <label htmlFor="skip-reason" className="block text-sm font-medium">
          Skip this job
        </label>
        <Input
          id="skip-reason"
          data-testid="detail-skip-reason"
          placeholder="Reason, e.g. scope unclear"
          maxLength={500}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <Button type="submit" variant="danger" size="sm" disabled={!reason.trim()} loading={skip.isPending}>
          Skip with reason
        </Button>
        <InlineError error={skip.error} />
      </form>
    </Card>
  );
}

function SpecList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
      <ul className="list-disc space-y-0.5 pl-5">
        {items.map((it, i) => (
          <li key={i}>{it}</li>
        ))}
      </ul>
    </div>
  );
}

function SkillList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
      {items.length ? (
        <div className="flex flex-wrap gap-1">
          {items.map((s) => (
            <Badge key={s}>{s}</Badge>
          ))}
        </div>
      ) : (
        <span className="text-muted">—</span>
      )}
    </div>
  );
}

function KV({ k, v, strong }: { k: string; v: ReactNode; strong?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-muted">{k}</dt>
      <dd className={cx("tabular-nums", strong && "text-base font-semibold")}>{v}</dd>
    </div>
  );
}
