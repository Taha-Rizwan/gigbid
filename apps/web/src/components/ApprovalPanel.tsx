"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { CheckCircle2, PencilLine, ShieldAlert, ThumbsDown, ThumbsUp } from "lucide-react";
import type { QueryKey } from "@tanstack/react-query";
import { useApproval } from "@/lib/hooks/queries";
import type { ApprovalRequest, ApprovalResult } from "@/lib/hooks/types";
import { humanize } from "@/lib/format";
import { Button, Field, Textarea } from "./ui";
import { InlineError } from "./ErrorState";

type Mode = "idle" | "edit" | "reject";

/**
 * The human-in-the-loop gate. Nothing is sent without an explicit Approve or
 * Edit; Reject requires a reason. Posts to POST /api/approvals/{thread_id}.
 */
export function ApprovalPanel({
  threadId,
  request,
  text,
  questions = [],
  answers = [],
  unsupportedCount = 0,
  invalidate = [],
  onResult,
}: {
  threadId: string;
  request: ApprovalRequest;
  /** The current draft text (cover letter or reply) that Edit starts from. */
  text: string;
  questions?: string[];
  answers?: string[];
  unsupportedCount?: number;
  invalidate?: QueryKey[];
  /** Called once the server accepted the decision (the panel may then unmount). */
  onResult?: (r: ApprovalResult) => void;
}) {
  const approval = useApproval(threadId, invalidate);
  const [mode, setMode] = useState<Mode>("idle");
  const [editedText, setEditedText] = useState(text);
  const [editedAnswers, setEditedAnswers] = useState<string[]>(() =>
    questions.map((_, i) => answers[i] ?? ""),
  );
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState<string | null>(null);
  const [result, setResult] = useState<ApprovalResult | null>(null);

  const blocked = request.compliance ? !request.compliance.allowed : false;
  const noun = request.kind === "message" ? "reply" : request.kind === "connects" ? "Connects spend" : "proposal";

  const done = (r: ApprovalResult) => {
    setResult(r);
    setMode("idle");
    onResult?.(r);
  };

  const approve = () => approval.mutate({ action: "approve" }, { onSuccess: done });

  const submitEdit = (e: FormEvent) => {
    e.preventDefault();
    approval.mutate(
      {
        action: "edit",
        edited_text: editedText,
        edited_answers: questions.length ? editedAnswers : null,
      },
      { onSuccess: done },
    );
  };

  const submitReject = (e: FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) {
      setReasonError("Please give a reason. GigBid learns from it.");
      return;
    }
    setReasonError(null);
    approval.mutate({ action: "reject", reason: reason.trim() }, { onSuccess: done });
  };

  if (result) {
    return (
      <section
        data-testid="approval-result"
        role="status"
        className="rounded-lg border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-100"
      >
        <p className="flex items-center gap-2 font-semibold">
          <CheckCircle2 aria-hidden className="size-4" />
          Decision recorded: {humanize(result.status)}
        </p>
        {result.detail && <p className="mt-1">{result.detail}</p>}
        {result.run_id && (
          <p className="mt-2">
            <Link className="font-medium underline" href={`/runs/${result.run_id}`}>
              Follow the run live
            </Link>
          </p>
        )}
      </section>
    );
  }

  return (
    <section
      aria-labelledby="approval-title"
      data-testid="approval-panel"
      className="rounded-lg border-2 border-accent/40 bg-surface p-4"
    >
      <h2 id="approval-title" className="text-base font-semibold">
        Your approval is required
      </h2>
      <p className="mt-1 text-sm text-muted">
        GigBid never sends a {noun} on its own. Approve it as is, edit it, or reject it with a reason.
      </p>

      {blocked && (
        <p className="mt-3 flex items-start gap-2 rounded-md bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950/50 dark:text-red-200">
          <ShieldAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          Compliance blocked this draft{request.compliance?.reason ? `: ${request.compliance.reason}` : ""}. Edit
          it or reject it.
        </p>
      )}
      {!blocked && unsupportedCount > 0 && (
        <p className="mt-3 rounded-md bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/50 dark:text-amber-100">
          {unsupportedCount} claim{unsupportedCount === 1 ? " is" : "s are"} still unsupported by your portfolio.
        </p>
      )}

      {mode === "idle" && (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            data-testid="approve-button"
            onClick={approve}
            loading={approval.isPending}
            disabled={blocked}
            title={blocked ? "Blocked by compliance" : undefined}
          >
            <ThumbsUp aria-hidden className="size-4" /> Approve and send
          </Button>
          <Button variant="secondary" data-testid="edit-button" onClick={() => setMode("edit")}>
            <PencilLine aria-hidden className="size-4" /> Edit
          </Button>
          <Button variant="danger" data-testid="reject-button" onClick={() => setMode("reject")}>
            <ThumbsDown aria-hidden className="size-4" /> Reject
          </Button>
        </div>
      )}

      {mode === "edit" && (
        <form className="mt-4 space-y-3" onSubmit={submitEdit} data-testid="edit-form">
          <Field label={request.kind === "message" ? "Reply text" : "Cover letter"} htmlFor="edit-text">
            <Textarea
              id="edit-text"
              data-testid="edit-textarea"
              rows={12}
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              required
            />
          </Field>
          {questions.map((q, i) => (
            <Field key={i} label={q} htmlFor={`edit-answer-${i}`}>
              <Textarea
                id={`edit-answer-${i}`}
                data-testid={`edit-answer-${i}`}
                rows={3}
                value={editedAnswers[i] ?? ""}
                onChange={(e) =>
                  setEditedAnswers((prev) => prev.map((a, j) => (j === i ? e.target.value : a)))
                }
              />
            </Field>
          ))}
          <p className="text-xs text-muted">
            Your edit is re-checked by the critic and compliance agents before it is sent.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" data-testid="submit-edit" loading={approval.isPending} disabled={!editedText.trim()}>
              Save edit and send
            </Button>
            <Button variant="ghost" onClick={() => setMode("idle")}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      {mode === "reject" && (
        <form className="mt-4 space-y-3" onSubmit={submitReject} noValidate data-testid="reject-form">
          <Field
            label="Why are you rejecting it?"
            htmlFor="reject-reason"
            hint="Required. Stored as a rejection reason and used to improve future drafts."
            error={reasonError}
          >
            <Textarea
              id="reject-reason"
              data-testid="reject-reason"
              rows={3}
              maxLength={1000}
              value={reason}
              aria-invalid={!!reasonError}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="danger" data-testid="submit-reject" loading={approval.isPending}>
              Reject {noun}
            </Button>
            <Button variant="ghost" onClick={() => setMode("idle")}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      <div className="mt-3">
        <InlineError error={approval.error} />
      </div>
    </section>
  );
}
