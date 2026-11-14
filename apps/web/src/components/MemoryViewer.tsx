"use client";

import { useState } from "react";
import { Brain, Trash2 } from "lucide-react";
import { useDeleteMemory, useMemory } from "@/lib/hooks/queries";
import type { MemoryItem } from "@/lib/hooks/types";
import { dateTime, humanize } from "@/lib/format";
import { Badge, Button } from "./ui";
import { EmptyState } from "./EmptyState";
import { ErrorState, InlineError } from "./ErrorState";
import { LoadingState } from "./LoadingState";

function describe(value: Record<string, unknown>): string {
  for (const k of ["summary", "text", "rule", "preference", "lesson", "note", "reason"]) {
    if (typeof value[k] === "string") return value[k] as string;
  }
  return "";
}

/** Lists what GigBid has learned (GET /api/memory), each deletable. */
export function MemoryViewer() {
  const memory = useMemory();
  const del = useDeleteMemory();
  const [confirming, setConfirming] = useState<string | null>(null);

  if (memory.isPending) return <LoadingState label="Loading memory" rows={2} />;
  if (memory.isError) return <ErrorState error={memory.error} onRetry={() => memory.refetch()} />;
  if (memory.data.length === 0) {
    return (
      <EmptyState
        icon={<Brain className="size-8" />}
        title="Nothing learned yet"
        description="As you approve, edit and reject drafts, GigBid stores style preferences and outcomes here."
      />
    );
  }

  const idOf = (m: MemoryItem) => `${m.namespace}/${m.key}`;

  return (
    <ul className="divide-y divide-line rounded-lg border border-line" data-testid="memory-list">
      {memory.data.map((m) => {
        const id = idOf(m);
        const text = describe(m.value);
        return (
          <li key={id} data-testid="memory-item" className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={m.namespace === "style" ? "accent" : "blue"}>{humanize(m.namespace)}</Badge>
                <span className="font-mono text-xs text-muted">{m.key}</span>
              </div>
              {text && <p className="mt-2 text-sm">{text}</p>}
              <details className="mt-2 text-xs">
                <summary className="cursor-pointer text-muted">Stored value</summary>
                <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded-md bg-subtle p-2 font-mono">
                  {JSON.stringify(m.value, null, 2)}
                </pre>
              </details>
              <p className="mt-1 text-xs text-muted">Updated {dateTime(m.updated_at ?? m.created_at)}</p>
            </div>
            <div className="flex shrink-0 gap-2">
              {confirming === id ? (
                <>
                  <Button
                    variant="danger"
                    size="sm"
                    data-testid="memory-confirm-delete"
                    loading={del.isPending}
                    onClick={() =>
                      del.mutate(
                        { namespace: m.namespace, key: m.key },
                        { onSuccess: () => setConfirming(null) },
                      )
                    }
                  >
                    Delete permanently
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setConfirming(null)}>
                    Cancel
                  </Button>
                </>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  data-testid="memory-delete"
                  aria-label={`Forget ${m.namespace} memory ${m.key}`}
                  onClick={() => setConfirming(id)}
                >
                  <Trash2 aria-hidden className="size-3.5" /> Forget
                </Button>
              )}
            </div>
          </li>
        );
      })}
      {del.isError && (
        <li className="p-3">
          <InlineError error={del.error} />
        </li>
      )}
    </ul>
  );
}
