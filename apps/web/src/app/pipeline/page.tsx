"use client";

import { RefreshCw } from "lucide-react";
import { usePipeline } from "@/lib/hooks/queries";
import { clock } from "@/lib/format";
import { Button, PageHeader } from "@/components/ui";
import { KanbanBoard } from "@/components/KanbanBoard";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";
import { EmptyState } from "@/components/EmptyState";

export default function PipelinePage() {
  const pipeline = usePipeline(); // polls every 15 s
  const total = pipeline.data ? Object.values(pipeline.data.columns).reduce((n, c) => n + (c?.length ?? 0), 0) : 0;

  return (
    <>
      <PageHeader
        title="Pipeline"
        description="Every proposal from draft to outcome. Updates every 15 seconds."
        actions={
          <>
            {pipeline.dataUpdatedAt > 0 && (
              <span className="text-xs text-muted" aria-live="polite">
                Updated {clock(new Date(pipeline.dataUpdatedAt).toISOString())}
              </span>
            )}
            <Button variant="secondary" size="sm" onClick={() => pipeline.refetch()} loading={pipeline.isFetching}>
              <RefreshCw aria-hidden className="size-3.5" /> Refresh
            </Button>
          </>
        }
      />
      {pipeline.isPending ? (
        <LoadingState label="Loading pipeline" />
      ) : pipeline.isError ? (
        <ErrorState title="Could not load the pipeline" error={pipeline.error} onRetry={() => pipeline.refetch()} />
      ) : total === 0 ? (
        <EmptyState title="No proposals yet" description="Approved proposals appear here and move as clients view, reply and hire." />
      ) : (
        <KanbanBoard columns={pipeline.data.columns} />
      )}
    </>
  );
}
