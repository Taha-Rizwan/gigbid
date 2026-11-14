"use client";

import { useState, type FormEvent } from "react";
import { Plus, Search, Trash2 } from "lucide-react";
import { useAddSearch, useDeleteSearch, useSearches } from "@/lib/hooks/queries";
import { money } from "@/lib/format";
import { Badge, Button, Field, Input } from "./ui";
import { ErrorState, InlineError } from "./ErrorState";
import { LoadingState } from "./LoadingState";

/** List, add (POST /api/searches) and delete saved searches. */
export function SavedSearchesEditor() {
  const searches = useSearches();
  const add = useAddSearch();
  const del = useDeleteSearch();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [minBudget, setMinBudget] = useState("");
  const [intervalMin, setIntervalMin] = useState("30");

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    add.mutate(
      {
        query: query.trim(),
        category: category.trim() || null,
        min_budget: minBudget ? Number(minBudget) : null,
        interval_minutes: Math.min(1440, Math.max(15, Number(intervalMin) || 30)),
        enabled: true,
      },
      {
        onSuccess: () => {
          setQuery("");
          setCategory("");
          setMinBudget("");
        },
      },
    );
  };

  return (
    <div className="space-y-4">
      {searches.isPending ? (
        <LoadingState label="Loading saved searches" rows={1} />
      ) : searches.isError ? (
        <ErrorState error={searches.error} onRetry={() => searches.refetch()} />
      ) : searches.data.length === 0 ? (
        <p className="text-sm text-muted">No saved searches yet. The scout runs each one on its interval.</p>
      ) : (
        <ul className="divide-y divide-line rounded-lg border border-line" data-testid="saved-search-list">
          {searches.data.map((s) => (
            <li key={s.search_id ?? s.query} data-testid="saved-search" className="flex items-center justify-between gap-3 px-3 py-2.5">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Search aria-hidden className="size-3.5 text-muted" />
                  {s.query}
                  {!s.enabled && <Badge>Paused</Badge>}
                </div>
                <div className="text-xs text-muted">
                  {[s.category, s.min_budget ? `min ${money(s.min_budget)}` : null, `every ${s.interval_minutes} min`]
                    .filter(Boolean)
                    .join(" · ")}
                </div>
              </div>
              {s.search_id && (
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Delete saved search ${s.query}`}
                  onClick={() => del.mutate(s.search_id!)}
                  disabled={del.isPending}
                >
                  <Trash2 aria-hidden className="size-4" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr_auto] lg:items-end">
        <Field label="Search query" htmlFor="ss-query">
          <Input
            id="ss-query"
            data-testid="search-query"
            placeholder="e.g. RAG chatbot"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </Field>
        <Field label="Category" htmlFor="ss-category">
          <Input id="ss-category" placeholder="Optional" value={category} onChange={(e) => setCategory(e.target.value)} />
        </Field>
        <Field label="Min budget ($)" htmlFor="ss-min">
          <Input id="ss-min" type="number" min={0} inputMode="decimal" value={minBudget} onChange={(e) => setMinBudget(e.target.value)} />
        </Field>
        <Field label="Every (min)" htmlFor="ss-interval">
          <Input id="ss-interval" type="number" min={15} max={1440} value={intervalMin} onChange={(e) => setIntervalMin(e.target.value)} />
        </Field>
        <Button type="submit" variant="secondary" data-testid="add-search" loading={add.isPending} disabled={!query.trim()}>
          <Plus aria-hidden className="size-4" /> Add
        </Button>
      </form>
      <InlineError error={add.error ?? del.error} />
    </div>
  );
}
