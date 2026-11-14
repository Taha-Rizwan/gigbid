"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  Gavel,
  Loader2,
  MessageSquareWarning,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { useRegenerate, useStudio } from "@/lib/hooks/queries";
import type {
  ApprovalResult,
  Claim,
  ComplianceVerdict,
  Critique,
  EvidenceItem,
  ParagraphOut,
  StudioOut,
} from "@/lib/hooks/types";
import { humanize } from "@/lib/format";
import { Badge, Button, Card, CardTitle, Input, PageHeader } from "@/components/ui";
import { CLAIM_STYLE, EvidenceHover, segmentParagraph } from "@/components/EvidenceHover";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { DryRunPreview } from "@/components/DryRunPreview";
import { RiskBadge } from "@/components/RiskBadge";
import { ErrorState, InlineError } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { EmptyState } from "@/components/EmptyState";

export default function StudioPage() {
  const { id } = useParams<{ id: string }>();
  // Everything, including pending_approval, comes from the server on every load.
  const studio = useStudio(id);

  if (studio.isPending) return <LoadingState label="Loading the draft" rows={4} />;
  if (studio.isError)
    return (
      <>
        <PageHeader title="Proposal studio" back={<BackToInbox />} />
        <ErrorState title="Could not load this draft" error={studio.error} onRetry={() => studio.refetch()} />
      </>
    );
  return <Studio data={studio.data} refreshing={studio.isFetching} />;
}

function BackToInbox() {
  return (
    <Link href="/inbox" className="inline-flex items-center gap-1 text-muted hover:text-fg">
      <ArrowLeft aria-hidden className="size-4" /> Inbox
    </Link>
  );
}

/** Critique issues that name a paragraph ("paragraph 2", "P2", "¶2") are pinned to it. */
function paragraphOf(issue: string): number | null {
  const m = issue.match(/(?:paragraph|para\.?|¶|\bp)\s*#?(\d+)/i);
  return m ? Number(m[1]) - 1 : null;
}

interface Comment {
  source: "critic" | "compliance";
  text: string;
  severity: "warn" | "block";
}

function collectComments(critiques: Critique[], compliance?: ComplianceVerdict | null) {
  const general: Comment[] = [];
  const byParagraph = new Map<number, Comment[]>();
  const push = (c: Comment, idx: number | null) => {
    if (idx === null) general.push(c);
    else byParagraph.set(idx, [...(byParagraph.get(idx) ?? []), c]);
  };
  const latest = critiques.at(-1);
  if (latest) {
    for (const issue of latest.issues ?? []) push({ source: "critic", text: issue, severity: "warn" }, paragraphOf(issue));
    if (latest.instructions) push({ source: "critic", text: latest.instructions, severity: "warn" }, null);
  }
  if (compliance) {
    for (const v of compliance.violations ?? []) push({ source: "compliance", text: v, severity: "block" }, paragraphOf(v));
    for (const r of compliance.redactions ?? []) push({ source: "compliance", text: `Redacted: ${r}`, severity: "warn" }, null);
  }
  return { general, byParagraph };
}

function Studio({ data, refreshing }: { data: StudioOut; refreshing: boolean }) {
  const [lastResult, setLastResult] = useState<ApprovalResult | null>(null);
  const pending = data.pending_approval;
  const evidence = new Map<string, EvidenceItem>();
  for (const e of [...(data.evidence ?? []), ...(pending?.evidence ?? [])]) evidence.set(e.evidence_id, e);
  const critiques = data.critiques?.length ? data.critiques : (pending?.critiques ?? []);
  const compliance = data.compliance ?? pending?.compliance ?? null;
  const comments = collectComments(critiques, compliance);
  const latestCritique = critiques.at(-1);
  const answers = data.screening_answers?.length ? data.screening_answers : (pending?.draft?.screening_answers ?? []);
  const questions = data.screening_questions ?? [];
  const draftText =
    pending?.draft?.cover_letter ?? pending?.reply?.text ?? data.paragraphs.map((p) => p.text).join("\n\n");
  const unsupportedNow = data.paragraphs.flatMap((p) => p.claims ?? []).filter((c) => c.label === "unsupported").length;
  const price = data.price ?? pending?.price ?? null;
  const risk = data.risk ?? pending?.risk ?? null;
  const working = data.status === "drafting" || data.status === "analysing";

  return (
    <>
      <PageHeader
        back={<BackToInbox />}
        title={data.job_title}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone={pending ? "amber" : "neutral"} data-testid="studio-status">
              {pending ? "Awaiting your approval" : humanize(data.status)}
            </Badge>
            <span>Draft v{data.version}</span>
            <Link className="underline" href={`/jobs/${data.job_id}`}>
              Job details
            </Link>
            {data.trace_url && (
              <a className="inline-flex items-center gap-1 underline" href={data.trace_url} target="_blank" rel="noreferrer">
                Trace <ExternalLink aria-hidden className="size-3" />
              </a>
            )}
            {refreshing && (
              <span className="inline-flex items-center gap-1 text-xs">
                <Loader2 aria-hidden className="size-3 animate-spin" /> syncing
              </span>
            )}
          </span>
        }
      />

      {lastResult && (
        <p
          role="status"
          data-testid="approval-outcome"
          className="mb-4 flex items-center gap-2 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-100"
        >
          <CheckCircle2 aria-hidden className="size-4" />
          Decision recorded: <strong>{humanize(lastResult.status)}</strong>
          {lastResult.detail && <span>· {lastResult.detail}</span>}
          {lastResult.run_id && (
            <Link className="underline" href={`/runs/${lastResult.run_id}`}>
              Follow the run
            </Link>
          )}
        </p>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Unsupported claims (before critic)" value={data.unsupported_before} testId="unsupported-before" />
        <Metric
          label="Unsupported claims (after critic)"
          value={data.unsupported_after}
          testId="unsupported-after"
          tone={data.unsupported_after === 0 ? "good" : "bad"}
        />
        <Metric
          label="Critic"
          value={latestCritique ? (latestCritique.passed ? "Passed" : "Issues") : "—"}
          tone={latestCritique ? (latestCritique.passed ? "good" : "bad") : undefined}
        />
        <Metric
          label="Compliance"
          value={compliance ? (compliance.allowed ? "Allowed" : "Blocked") : "—"}
          tone={compliance ? (compliance.allowed ? "good" : "bad") : undefined}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="space-y-4 lg:col-span-3">
          <Card>
            <CardTitle aside={<Legend />}>Draft</CardTitle>

            {comments.general.length > 0 && (
              <ul className="mb-4 space-y-2" aria-label="Review comments" data-testid="review-comments">
                {comments.general.map((c, i) => (
                  <CommentRow key={i} c={c} />
                ))}
              </ul>
            )}

            {working && data.paragraphs.length === 0 ? (
              <p role="status" className="flex items-center gap-2 text-sm text-muted">
                <Loader2 aria-hidden className="size-4 animate-spin" /> The writer is drafting…
              </p>
            ) : data.paragraphs.length === 0 ? (
              <EmptyState title="No draft yet" description="The writer agent has not produced a draft for this job." />
            ) : (
              <div className="space-y-5" data-testid="draft-editor">
                {data.paragraphs.map((p) => (
                  <Paragraph
                    key={`${data.version}-${p.index}`}
                    threadId={data.thread_id}
                    p={p}
                    evidence={evidence}
                    comments={comments.byParagraph.get(p.index) ?? []}
                  />
                ))}
              </div>
            )}

            {questions.length > 0 && (
              <div className="mt-6 space-y-3 border-t border-line pt-4">
                <h3 className="text-sm font-semibold">Screening questions</h3>
                {questions.map((q, i) => (
                  <div key={i} className="rounded-md bg-subtle p-3 text-sm">
                    <p className="font-medium">{q}</p>
                    <p className="mt-1 whitespace-pre-wrap">{answers[i] ?? <em className="text-muted">No answer drafted</em>}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-4 lg:col-span-2">
          {pending ? (
            <ApprovalPanel
              key={`${data.thread_id}-${data.version}`}
              threadId={data.thread_id}
              request={pending}
              text={draftText}
              questions={questions}
              answers={answers}
              unsupportedCount={unsupportedNow}
              onResult={setLastResult}
            />
          ) : (
            <Card data-testid="no-pending-approval">
              <CardTitle>Approval</CardTitle>
              <p className="text-sm text-muted">
                {working
                  ? "The agents are still working on this draft. It will appear here for approval."
                  : `Nothing is waiting for approval. Current status: ${humanize(data.status)}.`}
              </p>
            </Card>
          )}

          <DryRunPreview
            dryRun={pending?.dry_run ?? data.dry_run}
            fallbackText={draftText}
            questions={questions}
            fallbackAnswers={answers}
            price={price}
            kind={pending?.kind ?? "proposal"}
          />

          {risk && (
            <Card>
              <CardTitle aside={<RiskBadge level={risk.level} score={risk.score} />}>Risk check</CardTitle>
              {risk.injection_detected && (
                <p className="mb-2 flex items-center gap-2 text-sm font-medium text-red-700 dark:text-red-300">
                  <ShieldAlert aria-hidden className="size-4" /> Prompt injection detected in the job post
                </p>
              )}
              {risk.explanation && <p className="text-sm text-muted">{risk.explanation}</p>}
            </Card>
          )}
        </div>
      </div>
    </>
  );
}

function Legend() {
  return (
    <ul className="flex flex-wrap gap-3 text-xs" aria-label="Claim colour legend">
      {(Object.keys(CLAIM_STYLE) as Array<keyof typeof CLAIM_STYLE>).map((k) => {
        const s = CLAIM_STYLE[k];
        return (
          <li key={k} className={`inline-flex items-center gap-1 ${s.chip}`}>
            <s.Icon aria-hidden className="size-3.5" /> {s.label}
          </li>
        );
      })}
    </ul>
  );
}

function Metric({
  label,
  value,
  testId,
  tone,
}: {
  label: string;
  value: string | number;
  testId?: string;
  tone?: "good" | "bad";
}) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="text-xs text-muted">{label}</div>
      <div
        data-testid={testId}
        className={
          "mt-1 text-xl font-semibold tabular-nums " +
          (tone === "good" ? "text-emerald-700 dark:text-emerald-300" : tone === "bad" ? "text-red-700 dark:text-red-300" : "")
        }
      >
        {value}
      </div>
    </div>
  );
}

function CommentRow({ c }: { c: Comment }) {
  const Icon = c.source === "compliance" ? Gavel : MessageSquareWarning;
  return (
    <li
      data-testid={`comment-${c.source}`}
      className={
        "flex items-start gap-2 rounded-md border-l-4 px-3 py-2 text-sm " +
        (c.severity === "block"
          ? "border-red-500 bg-red-50 text-red-900 dark:bg-red-950/40 dark:text-red-100"
          : "border-amber-500 bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-100")
      }
    >
      <Icon aria-hidden className="mt-0.5 size-4 shrink-0" />
      <span>
        <span className="font-semibold">{c.source === "critic" ? "Critic" : "Compliance"}:</span> {c.text}
      </span>
    </li>
  );
}

function ClaimSpan({ claim, evidence, children }: { claim: Claim; evidence: Map<string, EvidenceItem>; children: ReactNode }) {
  const items = (claim.evidence_ids ?? [])
    .map((id) => evidence.get(id) ?? { evidence_id: id, type: "unknown", title: id, snippet: "Evidence not included in this response.", source: "", score: 0 });
  return (
    <EvidenceHover label={claim.label} evidence={items} note={claim.note}>
      {children}
    </EvidenceHover>
  );
}

function Paragraph({
  threadId,
  p,
  evidence,
  comments,
}: {
  threadId: string;
  p: ParagraphOut;
  evidence: Map<string, EvidenceItem>;
  comments: Comment[];
}) {
  const regen = useRegenerate(threadId);
  const [open, setOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const { segments, unmatched } = segmentParagraph(p.text, p.claims ?? []);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    regen.mutate(
      { paragraph_index: p.index, instruction: instruction.trim() || null },
      { onSuccess: () => setOpen(false) },
    );
  };

  return (
    <div data-testid="paragraph" data-index={p.index} className="group rounded-md">
      <p className="leading-7">
        {segments.map((s, i) =>
          s.claim ? (
            <ClaimSpan key={i} claim={s.claim} evidence={evidence}>
              {s.text}
            </ClaimSpan>
          ) : (
            <span key={i}>{s.text}</span>
          ),
        )}
      </p>

      {unmatched.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2 text-sm">
          <span className="text-xs text-muted">Claims:</span>
          {unmatched.map(({ claim, claimIndex }) => (
            <ClaimSpan key={claimIndex} claim={claim} evidence={evidence}>
              {claim.text}
            </ClaimSpan>
          ))}
        </div>
      )}

      {comments.length > 0 && (
        <ul className="mt-2 space-y-1.5" aria-label={`Comments on paragraph ${p.index + 1}`}>
          {comments.map((c, i) => (
            <CommentRow key={i} c={c} />
          ))}
        </ul>
      )}

      <div className="mt-2 flex flex-wrap items-center gap-2">
        {!open && (
          <Button
            size="sm"
            variant="ghost"
            data-testid={`regenerate-${p.index}`}
            onClick={() => setOpen(true)}
            aria-label={`Regenerate paragraph ${p.index + 1}`}
          >
            <RefreshCw aria-hidden className="size-3.5" /> Regenerate this paragraph
          </Button>
        )}
        {regen.data && (
          <span role="status" className="text-xs text-muted">
            Regenerating…{" "}
            <Link className="text-accent underline" href={`/runs/${regen.data.run_id}`}>
              watch run
            </Link>
          </span>
        )}
      </div>
      {open && (
        <form onSubmit={submit} className="mt-2 flex flex-col gap-2 sm:flex-row">
          <label htmlFor={`regen-${p.index}`} className="sr-only">
            Instruction for paragraph {p.index + 1}
          </label>
          <Input
            id={`regen-${p.index}`}
            data-testid={`regenerate-instruction-${p.index}`}
            placeholder="Optional: e.g. mention the churn model, shorter"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" data-testid={`regenerate-submit-${p.index}`} loading={regen.isPending}>
              Regenerate
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
      <InlineError error={regen.error} />
    </div>
  );
}
