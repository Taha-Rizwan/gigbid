import { CheckCircle2, XCircle } from "lucide-react";
import type { RequirementMatch } from "@/lib/hooks/types";
import { EmptyState } from "./EmptyState";
import { humanize } from "@/lib/format";

/** Requirement → portfolio evidence matrix, with a covered / not covered indicator per row. */
export function EvidenceMatrix({ matches }: { matches: RequirementMatch[] }) {
  if (matches.length === 0) {
    return (
      <EmptyState
        title="No requirements matched yet"
        description="Run Analyze to have the fit matcher map each requirement to your portfolio."
      />
    );
  }
  const covered = matches.filter((m) => m.covered).length;
  return (
    <div data-testid="evidence-matrix">
      <p className="mb-3 text-sm text-muted">
        <span className="font-semibold text-fg tabular-nums">
          {covered}/{matches.length}
        </span>{" "}
        requirements backed by portfolio evidence.
      </p>
      {/* A list on phones, a table-like grid from md up. */}
      <div role="table" aria-label="Requirement to evidence matrix" className="divide-y divide-line rounded-lg border border-line">
        <div role="row" className="hidden grid-cols-[minmax(0,2fr)_minmax(0,3fr)_7rem] gap-4 bg-subtle px-4 py-2 text-xs font-semibold uppercase tracking-wide text-muted md:grid">
          <span role="columnheader">Requirement</span>
          <span role="columnheader">Evidence</span>
          <span role="columnheader">Covered</span>
        </div>
        {matches.map((m, i) => (
          <div
            role="row"
            key={i}
            data-testid="matrix-row"
            data-covered={m.covered}
            className="grid gap-2 px-4 py-3 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)_7rem] md:gap-4"
          >
            <div role="cell" className="text-sm font-medium">
              {m.requirement}
              {m.rationale && <p className="mt-1 text-xs font-normal text-muted">{m.rationale}</p>}
            </div>
            <div role="cell" className="flex flex-wrap gap-1.5">
              {(m.evidence ?? []).length === 0 ? (
                <span className="text-sm text-muted">No evidence found</span>
              ) : (
                m.evidence!.map((e) => (
                  <span
                    key={e.evidence_id}
                    title={e.snippet}
                    className="inline-block max-w-full rounded-md border border-line bg-subtle px-2 py-1 text-xs [overflow-wrap:normal]"
                  >
                    <span className="font-medium">{e.title}</span>
                    <span className="whitespace-nowrap text-muted"> · {humanize(e.type)}</span>
                    {e.score > 0 && <span className="whitespace-nowrap tabular-nums text-muted"> · {e.score.toFixed(2)}</span>}
                  </span>
                ))
              )}
            </div>
            <div role="cell" className="text-sm">
              {m.covered ? (
                <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 aria-hidden className="size-4" /> Covered
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-red-700 dark:text-red-300">
                  <XCircle aria-hidden className="size-4" /> Not covered
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
