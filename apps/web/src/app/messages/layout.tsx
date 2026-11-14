"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { ConversationList } from "@/components/ConversationList";
import { PageHeader } from "@/components/ui";
import { cx } from "@/lib/format";

/** Two panes on large screens; on phones the list and the thread are separate pages. */
export default function MessagesLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const inThread = pathname !== "/messages";
  return (
    <>
      <PageHeader title="Messages" description="Client threads. Every reply waits for your approval before it is sent." />
      <div className="grid gap-4 lg:grid-cols-[20rem_minmax(0,1fr)]">
        <div className={cx(inThread && "hidden lg:block")}>
          <ConversationList />
        </div>
        <div className={cx("min-w-0", !inThread && "hidden lg:block")}>{children}</div>
      </div>
    </>
  );
}
