"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AlertTriangle, MessagesSquare } from "lucide-react";
import { useConversations } from "@/lib/hooks/queries";
import { cx, dateTime, humanize } from "@/lib/format";
import { Badge } from "./ui";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";

export function ConversationList() {
  const convs = useConversations();
  const pathname = usePathname();

  if (convs.isPending) return <LoadingState label="Loading conversations" rows={3} />;
  if (convs.isError) return <ErrorState error={convs.error} onRetry={() => convs.refetch()} />;
  if (convs.data.length === 0)
    return (
      <EmptyState
        icon={<MessagesSquare className="size-8" />}
        title="No conversations yet"
        description="When a client replies to a proposal, the thread shows up here."
      />
    );

  return (
    <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-surface" data-testid="conversation-list">
      {convs.data.map((c) => {
        const href = `/messages/${c.conversation_id}`;
        const active = pathname === href;
        const scam = (c.flags ?? []).some((f) => /scam|off.?platform|payment/i.test(f)) || c.intent === "scam_signal";
        return (
          <li key={c.conversation_id}>
            <Link
              href={href}
              aria-current={active ? "page" : undefined}
              data-testid="conversation-item"
              className={cx("block px-4 py-3 hover:bg-subtle", active && "bg-accent-soft")}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={cx("truncate text-sm", c.unread ? "font-semibold" : "font-medium")}>
                  {c.client_name ?? "Client"}
                  {c.unread && <span className="sr-only"> (unread)</span>}
                </span>
                <span className="shrink-0 text-xs text-muted">{dateTime(c.last_message_at)}</span>
              </div>
              <div className="truncate text-xs text-muted">{c.job_title ?? "—"}</div>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {c.unread && <Badge tone="accent">New</Badge>}
                {c.pending_reply && <Badge tone="amber">Reply awaiting approval</Badge>}
                {c.intent && <Badge>{humanize(c.intent)}</Badge>}
                {scam && (
                  <Badge tone="red">
                    <AlertTriangle aria-hidden className="size-3" /> Scam signal
                  </Badge>
                )}
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
