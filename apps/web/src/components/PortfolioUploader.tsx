"use client";

import { useRef, useState, type FormEvent } from "react";
import { FileUp, FolderOpen } from "lucide-react";
import { usePortfolio, useUploadPortfolio } from "@/lib/hooks/queries";
import { Badge, Button } from "./ui";
import { InlineError } from "./ErrorState";
import { LoadingState } from "./LoadingState";

/** Multipart upload to POST /api/portfolio/upload, plus the current portfolio list. */
export function PortfolioUploader() {
  const portfolio = usePortfolio();
  const upload = useUploadPortfolio();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (files.length === 0) return;
    upload.mutate(files, {
      onSuccess: () => {
        setFiles([]);
        if (inputRef.current) inputRef.current.value = "";
      },
    });
  };

  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="rounded-lg border border-dashed border-line bg-subtle/50 p-4">
        <label htmlFor="portfolio-files" className="flex items-center gap-2 text-sm font-medium">
          <FileUp aria-hidden className="size-4" /> Portfolio files
        </label>
        <p className="mt-1 text-xs text-muted">
          Case studies, READMEs, CVs, past proposals (PDF, Markdown, text, JSON). Every claim in a draft must
          cite one of these.
        </p>
        <input
          ref={inputRef}
          id="portfolio-files"
          data-testid="portfolio-input"
          type="file"
          multiple
          accept=".pdf,.md,.markdown,.txt,.json,.jsonl,.docx,.csv"
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          className="mt-3 block w-full text-sm file:mr-3 file:rounded-md file:border file:border-line file:bg-surface file:px-3 file:py-1.5 file:text-sm file:font-medium"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button type="submit" data-testid="portfolio-upload" loading={upload.isPending} disabled={files.length === 0}>
            Upload {files.length > 0 ? `${files.length} file${files.length > 1 ? "s" : ""}` : ""}
          </Button>
          {upload.data && (
            <p role="status" data-testid="upload-result" className="text-sm text-emerald-700 dark:text-emerald-300">
              Added {upload.data.added} item{upload.data.added === 1 ? "" : "s"} ({upload.data.chunks} chunks indexed).
            </p>
          )}
        </div>
        <div className="mt-2">
          <InlineError error={upload.error} />
        </div>
      </form>

      {portfolio.isPending ? (
        <LoadingState label="Loading portfolio" rows={1} />
      ) : portfolio.isError ? (
        <InlineError error={portfolio.error} />
      ) : portfolio.data.length === 0 ? (
        <p className="flex items-center gap-2 text-sm text-muted">
          <FolderOpen aria-hidden className="size-4" /> No portfolio items yet.
        </p>
      ) : (
        <ul className="grid gap-2 sm:grid-cols-2" data-testid="portfolio-list">
          {portfolio.data.map((p) => (
            <li key={p.evidence_id} className="rounded-md border border-line bg-surface p-3 text-sm">
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium">{p.title}</span>
                <Badge>{p.type}</Badge>
              </div>
              {p.project && <div className="text-xs text-muted">{p.project}</div>}
              {(p.skills?.length ?? 0) > 0 && <div className="mt-1 text-xs text-muted">{p.skills!.slice(0, 6).join(" · ")}</div>}
              {p.synthetic && <div className="mt-1 text-[11px] text-muted">Synthetic sample</div>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
