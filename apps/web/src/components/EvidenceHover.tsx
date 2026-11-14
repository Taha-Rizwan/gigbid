"use client";

import { useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { CheckCircle2, CircleAlert, CircleHelp } from "lucide-react";
import type { ClaimLabel, EvidenceItem } from "@/lib/hooks/types";
import { cx } from "@/lib/format";

export const CLAIM_STYLE: Record<
  ClaimLabel,
  { label: string; mark: string; chip: string; Icon: typeof CheckCircle2 }
> = {
  supported: {
    label: "Supported",
    mark: "decoration-emerald-500 bg-emerald-50/70 dark:bg-emerald-950/40",
    chip: "text-emerald-700 dark:text-emerald-300",
    Icon: CheckCircle2,
  },
  partly_supported: {
    label: "Partly supported",
    mark: "decoration-amber-500 bg-amber-50/70 dark:bg-amber-950/40",
    chip: "text-amber-700 dark:text-amber-300",
    Icon: CircleHelp,
  },
  unsupported: {
    label: "Unsupported",
    mark: "decoration-red-500 decoration-wavy bg-red-50/70 dark:bg-red-950/40",
    chip: "text-red-700 dark:text-red-300",
    Icon: CircleAlert,
  },
};

/**
 * Wraps a claim in the draft. Its evidence appears on hover AND on keyboard
 * focus (the trigger is focusable and the card is linked via aria-describedby).
 * Escape dismisses it.
 */
export function EvidenceHover({
  label,
  evidence,
  note,
  children,
  testId,
}: {
  label: ClaimLabel;
  evidence: EvidenceItem[];
  note?: string;
  children: ReactNode;
  testId?: string;
}) {
  const id = useId();
  const triggerRef = useRef<HTMLSpanElement>(null);
  const cardRef = useRef<HTMLSpanElement>(null);
  const [hover, setHover] = useState(false);
  const [focus, setFocus] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const open = (hover || focus) && !dismissed;
  const style = CLAIM_STYLE[label] ?? CLAIM_STYLE.unsupported;

  // Position the card in the viewport (fixed), clamped so it never causes horizontal scroll.
  useLayoutEffect(() => {
    if (!open || !triggerRef.current || !cardRef.current) return;
    const card = cardRef.current;
    const place = () => {
      const r = triggerRef.current!.getBoundingClientRect();
      const width = Math.min(336, window.innerWidth - 16);
      const cardH = card.offsetHeight || 160;
      const left = Math.max(8, Math.min(r.left, window.innerWidth - width - 8));
      const below = r.bottom + 6;
      const top = below + cardH > window.innerHeight && r.top - cardH - 6 > 0 ? r.top - cardH - 6 : below;
      card.style.top = `${top}px`;
      card.style.left = `${left}px`;
      card.style.visibility = "visible";
    };
    place();
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open]);

  return (
    <span
      ref={triggerRef}
      tabIndex={0}
      aria-describedby={open ? id : undefined}
      data-testid={testId ?? "claim"}
      data-label={label}
      onMouseEnter={() => {
        setHover(true);
        setDismissed(false);
      }}
      onMouseLeave={() => setHover(false)}
      onFocus={() => {
        setFocus(true);
        setDismissed(false);
      }}
      onBlur={() => setFocus(false)}
      onKeyDown={(e) => {
        if (e.key === "Escape") setDismissed(true);
      }}
      className={cx(
        "cursor-help rounded-sm underline decoration-2 underline-offset-4",
        style.mark,
      )}
    >
      {children}
      <span className="sr-only"> ({style.label})</span>
      {open && (
        <span
          ref={cardRef}
          id={id}
          role="tooltip"
          data-testid="evidence-card"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            visibility: "hidden",
            width: "min(21rem, calc(100vw - 1rem))",
          }}
          className="z-50 block rounded-lg border border-line bg-surface p-3 text-left text-sm font-normal text-fg no-underline shadow-lg"
        >
          <span className={cx("mb-2 flex items-center gap-1.5 text-xs font-semibold", style.chip)}>
            <style.Icon aria-hidden className="size-3.5" />
            {style.label}
            <span className="font-normal text-muted">
              · {evidence.length} evidence item{evidence.length === 1 ? "" : "s"}
            </span>
          </span>
          {note && <span className="mb-2 block text-xs text-muted">{note}</span>}
          {evidence.length === 0 ? (
            <span className="block text-xs text-muted">
              No portfolio evidence backs this claim. Edit or remove it before approving.
            </span>
          ) : (
            <span className="block space-y-2">
              {evidence.map((ev) => (
                <span key={ev.evidence_id} className="block rounded-md bg-subtle p-2">
                  <span className="block text-xs font-semibold">{ev.title}</span>
                  <span className="block text-[11px] uppercase tracking-wide text-muted">
                    {ev.type}
                    {ev.project ? ` · ${ev.project}` : ""}
                    {ev.date ? ` · ${ev.date}` : ""}
                  </span>
                  <span className="mt-1 block text-xs leading-relaxed">{ev.snippet}</span>
                  {ev.outcome && (
                    <span className="mt-1 block text-xs text-emerald-700 dark:text-emerald-300">
                      Outcome: {ev.outcome}
                    </span>
                  )}
                  <span className="mt-1 block font-mono text-[10px] text-muted">
                    {ev.evidence_id}
                    {ev.source ? ` · ${ev.source}` : ""}
                  </span>
                </span>
              ))}
            </span>
          )}
        </span>
      )}
    </span>
  );
}

/** Splits a paragraph into plain text and claim spans (first occurrence of each claim). */
export function segmentParagraph<C extends { text: string }>(
  text: string,
  claims: C[],
): { segments: Array<{ text: string; claim?: C; claimIndex?: number }>; unmatched: Array<{ claim: C; claimIndex: number }> } {
  const found: Array<{ start: number; end: number; claim: C; claimIndex: number }> = [];
  const unmatched: Array<{ claim: C; claimIndex: number }> = [];
  claims.forEach((claim, claimIndex) => {
    const needle = claim.text.trim();
    const start = needle ? text.indexOf(needle) : -1;
    const overlaps = found.some((f) => start < f.end && start + needle.length > f.start);
    if (start === -1 || overlaps) unmatched.push({ claim, claimIndex });
    else found.push({ start, end: start + needle.length, claim, claimIndex });
  });
  found.sort((a, b) => a.start - b.start);
  const segments: Array<{ text: string; claim?: C; claimIndex?: number }> = [];
  let cursor = 0;
  for (const f of found) {
    if (f.start > cursor) segments.push({ text: text.slice(cursor, f.start) });
    segments.push({ text: text.slice(f.start, f.end), claim: f.claim, claimIndex: f.claimIndex });
    cursor = f.end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor) });
  return { segments, unmatched };
}
