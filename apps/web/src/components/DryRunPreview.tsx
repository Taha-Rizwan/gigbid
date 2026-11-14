import { CheckCircle2, Coins, Send, ShieldAlert } from "lucide-react";
import type { DryRun, PriceQuote } from "@/lib/hooks/types";
import { price as fmtPrice } from "@/lib/format";
import { Badge } from "./ui";

/**
 * Exactly what will be sent if the human approves, from the marketplace's
 * dry-run endpoint (nothing is sent or spent to produce it), plus Connects cost.
 */
export function DryRunPreview({
  dryRun,
  fallbackText,
  questions = [],
  fallbackAnswers = [],
  price,
  kind = "proposal",
}: {
  dryRun?: Record<string, unknown> | null;
  fallbackText?: string;
  questions?: string[];
  fallbackAnswers?: string[];
  price?: PriceQuote | null;
  kind?: "proposal" | "message" | "connects";
}) {
  const dr = (dryRun ?? {}) as DryRun;
  const ws = dr.would_send ?? {};
  const text =
    (typeof ws.cover_letter === "string" && ws.cover_letter) ||
    (typeof ws.text === "string" && ws.text) ||
    fallbackText ||
    "";
  const answers = Array.isArray(ws.screening_answers) ? ws.screening_answers : fallbackAnswers;
  const bid = typeof ws.bid_amount === "number" ? ws.bid_amount : price?.amount;
  const rateType = ws.rate_type ?? price?.rate_type;
  const connects = typeof dr.connects_cost === "number" ? dr.connects_cost : price?.connects_cost;
  const policy = dr.policy_check;
  const isMessage = kind === "message";

  return (
    <section
      aria-labelledby="dryrun-title"
      data-testid="dry-run-preview"
      className="rounded-lg border border-line bg-surface"
    >
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
        <h2 id="dryrun-title" className="flex items-center gap-2 text-sm font-semibold">
          <Send aria-hidden className="size-4" /> Dry-run preview
        </h2>
        <span className="text-xs text-muted">Nothing is sent until you approve</span>
      </header>

      <dl className="grid grid-cols-2 gap-3 border-b border-line px-4 py-3 text-sm sm:grid-cols-4">
        {!isMessage && (
          <div>
            <dt className="text-xs text-muted">Bid</dt>
            <dd className="font-semibold tabular-nums" data-testid="dry-run-bid">
              {fmtPrice(bid, rateType)}
            </dd>
          </div>
        )}
        <div>
          <dt className="text-xs text-muted">Connects cost</dt>
          <dd className="flex items-center gap-1 font-semibold tabular-nums" data-testid="dry-run-connects">
            <Coins aria-hidden className="size-3.5 text-muted" />
            {connects ?? (isMessage ? 0 : "—")}
          </dd>
        </div>
        {typeof dr.balance_after === "number" && (
          <div>
            <dt className="text-xs text-muted">Balance after</dt>
            <dd className="font-semibold tabular-nums">{dr.balance_after}</dd>
          </div>
        )}
        {policy && (
          <div>
            <dt className="text-xs text-muted">Policy check</dt>
            <dd>
              {policy.ok ? (
                <Badge tone="green">
                  <CheckCircle2 aria-hidden className="size-3" /> Passes
                </Badge>
              ) : (
                <Badge tone="red">
                  <ShieldAlert aria-hidden className="size-3" /> Violations
                </Badge>
              )}
            </dd>
          </div>
        )}
      </dl>

      {policy && !policy.ok && (policy.violations?.length ?? 0) > 0 && (
        <ul className="list-disc space-y-1 border-b border-line px-8 py-3 text-sm text-red-700 dark:text-red-300">
          {policy.violations!.map((v, i) => (
            <li key={i}>{v}</li>
          ))}
        </ul>
      )}

      <div className="px-4 py-3">
        <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">
          {isMessage ? "Message" : "Cover letter"}
        </h3>
        {text ? (
          <pre
            data-testid="dry-run-text"
            className="max-h-80 overflow-y-auto whitespace-pre-wrap break-words rounded-md bg-subtle p-3 font-sans text-sm leading-relaxed"
          >
            {text}
          </pre>
        ) : (
          <p className="text-sm text-muted">No preview available yet.</p>
        )}
        {questions.length > 0 && (
          <div className="mt-3 space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Screening answers</h3>
            {questions.map((q, i) => (
              <div key={i} className="rounded-md bg-subtle p-3 text-sm">
                <p className="font-medium">{q}</p>
                <p className="mt-1 whitespace-pre-wrap">{answers[i] ?? <em className="text-muted">No answer</em>}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
