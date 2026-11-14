import Link from "next/link";
import { Coins, MessagesSquare } from "lucide-react";
import type { PipelineCard, Stage } from "@/lib/hooks/types";
import { STAGES } from "@/lib/hooks/types";
import { cx, dateTime, money } from "@/lib/format";

const STAGE_LABEL: Record<Stage, string> = {
  drafted: "Drafted",
  submitted: "Submitted",
  viewed: "Viewed",
  replied: "Replied",
  interview: "Interview",
  hired: "Hired",
  lost: "Lost",
};

const STAGE_DOT: Record<Stage, string> = {
  drafted: "bg-zinc-400",
  submitted: "bg-sky-500",
  viewed: "bg-indigo-500",
  replied: "bg-violet-500",
  interview: "bg-amber-500",
  hired: "bg-emerald-500",
  lost: "bg-red-400",
};

/**
 * Read-only kanban. Columns wrap (1 → 2 → 4 → 7 per row) instead of scrolling
 * sideways, so the page never scrolls horizontally on a phone.
 */
export function KanbanBoard({ columns }: { columns: Partial<Record<Stage, PipelineCard[]>> }) {
  return (
    <div
      data-testid="kanban-board"
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 2xl:grid-cols-7"
    >
      {STAGES.map((stage) => {
        const cards = columns[stage] ?? [];
        return (
          <section
            key={stage}
            aria-labelledby={`col-${stage}`}
            data-testid={`kanban-column-${stage}`}
            className="flex min-w-0 flex-col rounded-lg border border-line bg-subtle/60"
          >
            <header className="flex items-center justify-between px-3 py-2">
              <h2 id={`col-${stage}`} className="flex items-center gap-2 text-sm font-semibold">
                <span aria-hidden className={cx("size-2 rounded-full", STAGE_DOT[stage])} />
                {STAGE_LABEL[stage]}
              </h2>
              <span className="rounded-full bg-surface px-2 text-xs tabular-nums text-muted" aria-label={`${cards.length} cards`}>
                {cards.length}
              </span>
            </header>
            <ul className="flex flex-1 flex-col gap-2 px-2 pb-2">
              {cards.length === 0 && (
                <li className="rounded-md border border-dashed border-line px-3 py-4 text-center text-xs text-muted">
                  Nothing here
                </li>
              )}
              {cards.map((c) => (
                <li key={c.job_id + (c.proposal_id ?? "")} data-testid="kanban-card" className="rounded-md border border-line bg-surface p-3 shadow-xs">
                  <Link href={`/jobs/${c.job_id}`} className="text-sm font-medium hover:underline">
                    {c.title}
                  </Link>
                  <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                    {c.bid_amount !== null && c.bid_amount !== undefined && (
                      <span className="tabular-nums">{money(c.bid_amount)}</span>
                    )}
                    {c.connects_spent !== null && c.connects_spent !== undefined && (
                      <span className="inline-flex items-center gap-1 tabular-nums">
                        <Coins aria-hidden className="size-3" />
                        {c.connects_spent}
                      </span>
                    )}
                    {c.updated_at && <span>{dateTime(c.updated_at)}</span>}
                  </div>
                  {c.conversation_thread_id && (
                    <Link
                      href={`/messages/${c.conversation_thread_id}`}
                      className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
                    >
                      <MessagesSquare aria-hidden className="size-3" /> Open thread
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
