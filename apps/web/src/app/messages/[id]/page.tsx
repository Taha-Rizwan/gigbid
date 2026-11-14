"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { AlertTriangle, ArrowLeft, CalendarClock, Sparkles, WandSparkles } from "lucide-react";
import { keys, useConversation, useDraftReply } from "@/lib/hooks/queries";
import type { ApprovalRequest, ApprovalResult, ConversationOut } from "@/lib/hooks/types";
import { cx, dateTime, humanize } from "@/lib/format";
import { Badge, Button, Card, CardTitle } from "@/components/ui";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { DryRunPreview } from "@/components/DryRunPreview";
import { ErrorState, InlineError } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";

export default function ThreadPage() {
  const { id } = useParams<{ id: string }>();
  const conv = useConversation(id);

  return (
    <div className="space-y-4">
      <Link href="/messages" className="inline-flex items-center gap-1 text-sm text-muted hover:text-fg lg:hidden">
        <ArrowLeft aria-hidden className="size-4" /> All conversations
      </Link>
      {conv.isPending ? (
        <LoadingState label="Loading thread" rows={3} />
      ) : conv.isError ? (
        <ErrorState title="Could not load this thread" error={conv.error} onRetry={() => conv.refetch()} />
      ) : (
        <Thread c={conv.data} />
      )}
    </div>
  );
}

const SCAM = /scam|off.?platform|payment|telegram|whatsapp|crypto|gift.?card|outside/i;

function Thread({ c }: { c: ConversationOut }) {
  const draft = useDraftReply();
  const [result, setResult] = useState<ApprovalResult | null>(null);
  const flags = c.flags ?? [];
  const slots = c.proposed_slots ?? [];
  const scamFlags = flags.filter((f) => SCAM.test(f));
  const otherFlags = flags.filter((f) => !SCAM.test(f));
  const isScam = scamFlags.length > 0 || c.intent === "scam_signal";
  const canApprove = c.awaiting_approval && !!c.graph_thread_id && !!c.suggested_reply;

  // The approvals endpoint is shared with proposals; build the request the panel needs.
  const request: ApprovalRequest | null = canApprove
    ? { kind: "message", thread_id: c.graph_thread_id!, evidence: [], critiques: [] }
    : null;

  return (
    <>
      <Card>
        <CardTitle
          aside={
            <Button
              variant="secondary"
              size="sm"
              data-testid="draft-reply"
              loading={draft.isPending}
              onClick={() => draft.mutate(c.conversation_id)}
            >
              <WandSparkles aria-hidden className="size-3.5" /> Draft reply
            </Button>
          }
        >
          {c.client_name ?? "Client"}
          {c.job_title && <span className="block text-sm font-normal text-muted">{c.job_title}</span>}
        </CardTitle>
        {draft.data && (
          <p role="status" className="mb-3 text-sm">
            Drafting a reply.{" "}
            <Link className="text-accent underline" href={`/runs/${draft.data.run_id}`}>
              Watch the run
            </Link>
          </p>
        )}
        <InlineError error={draft.error} />

        {(isScam || otherFlags.length > 0 || c.intent) && (
          <div className="mb-4 space-y-2">
            {isScam && (
              <p data-testid="scam-warning" role="alert" className="flex items-start gap-2 rounded-md bg-red-50 p-3 text-sm text-red-900 dark:bg-red-950/50 dark:text-red-100">
                <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
                <span>
                  <strong>Possible scam.</strong> {scamFlags.map(humanize).join(", ") || "The client shows scam signals."} Never
                  move payment or contact off-platform.
                </span>
              </p>
            )}
            <div className="flex flex-wrap gap-1.5">
              {c.intent && <Badge tone="accent">Intent: {humanize(c.intent)}</Badge>}
              {otherFlags.map((f) => (
                <Badge key={f} tone="amber">
                  {humanize(f)}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <ol className="space-y-3" aria-label="Messages" data-testid="message-list">
          {c.messages.length === 0 && <li className="text-sm text-muted">No messages yet.</li>}
          {c.messages.map((m) => (
            <li key={m.message_id} className={cx("flex", m.sender === "freelancer" ? "justify-end" : "justify-start")}>
              <div
                className={cx(
                  "max-w-[85%] rounded-lg px-3 py-2 text-sm",
                  m.sender === "freelancer" ? "bg-accent text-accent-fg" : "border border-line bg-subtle",
                )}
              >
                <span className="sr-only">{m.sender === "freelancer" ? "You" : "Client"}: </span>
                <p className="whitespace-pre-wrap">{m.text}</p>
                <p className={cx("mt-1 text-[11px]", m.sender === "freelancer" ? "opacity-80" : "text-muted")}>
                  {dateTime(m.sent_at)}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </Card>

      {slots.length > 0 && (
        <Card data-testid="proposed-slots">
          <CardTitle>
            <span className="inline-flex items-center gap-2">
              <CalendarClock aria-hidden className="size-4" /> Proposed interview slots
            </span>
          </CardTitle>
          <ul className="flex flex-wrap gap-2">
            {slots.map((s) => (
              <li key={s} className="rounded-md border border-line bg-subtle px-3 py-1.5 text-sm tabular-nums">
                {/^\d{4}-\d{2}-\d{2}T/.test(s) ? dateTime(s) : s}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {c.suggested_reply && (
        <Card data-testid="suggested-reply">
          <CardTitle>
            <span className="inline-flex items-center gap-2">
              <Sparkles aria-hidden className="size-4" /> Suggested reply
            </span>
          </CardTitle>
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{c.suggested_reply}</p>
        </Card>
      )}

      {result && (
        <p role="status" data-testid="approval-outcome" className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-100">
          Decision recorded: <strong>{humanize(result.status)}</strong>
          {result.detail && ` · ${result.detail}`}
        </p>
      )}

      {request && (
        <>
          <ApprovalPanel
            key={c.graph_thread_id! + (c.suggested_reply ?? "")}
            threadId={c.graph_thread_id!}
            request={request}
            text={c.suggested_reply ?? ""}
            invalidate={[keys.conversation(c.conversation_id), keys.conversations]}
            onResult={setResult}
          />
          <DryRunPreview kind="message" fallbackText={c.suggested_reply ?? ""} />
        </>
      )}
      {!request && c.awaiting_approval && (
        <p className="text-sm text-muted">A reply is being prepared for your approval…</p>
      )}
    </>
  );
}
