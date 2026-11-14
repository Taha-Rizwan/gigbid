"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  Activity,
  BarChart3,
  Inbox,
  KanbanSquare,
  LogOut,
  Menu,
  MessagesSquare,
  Settings,
  X,
} from "lucide-react";
import { DegradedBanner } from "./DegradedBanner";
import { useLogout, useMe } from "@/lib/hooks/queries";
import { cx } from "@/lib/format";

const NAV = [
  { href: "/inbox", label: "Inbox", icon: Inbox, match: ["/inbox", "/jobs", "/studio"] },
  { href: "/pipeline", label: "Pipeline", icon: KanbanSquare, match: ["/pipeline"] },
  { href: "/messages", label: "Messages", icon: MessagesSquare, match: ["/messages"] },
  { href: "/runs", label: "Agent runs", icon: Activity, match: ["/runs"] },
  { href: "/analytics", label: "Analytics", icon: BarChart3, match: ["/analytics"] },
  { href: "/settings", label: "Settings", icon: Settings, match: ["/settings"] },
];

function Brand() {
  return (
    <Link href="/inbox" className="flex items-center gap-2 font-semibold tracking-tight">
      <span
        aria-hidden
        className="grid size-7 place-items-center rounded-md bg-accent text-xs font-bold text-accent-fg"
      >
        GB
      </span>
      GigBid
    </Link>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <ul className="space-y-0.5">
      {NAV.map(({ href, label, icon: Icon, match }) => {
        const active = match.some((m) => pathname === m || pathname.startsWith(m + "/"));
        return (
          <li key={href}>
            <Link
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cx(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium",
                active ? "bg-accent-soft text-accent" : "text-muted hover:bg-subtle hover:text-fg",
              )}
            >
              <Icon aria-hidden className="size-4" />
              {label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function UserBox() {
  const me = useMe();
  const logout = useLogout();
  const router = useRouter();
  return (
    <div className="flex items-center justify-between gap-2 border-t border-line px-3 pt-3">
      <div className="min-w-0 text-sm">
        <div className="truncate font-medium">{me.data?.name ?? "…"}</div>
        <div className="truncate text-xs text-muted">{me.data?.email}</div>
      </div>
      <button
        type="button"
        className="rounded-md p-2 text-muted hover:bg-subtle hover:text-fg"
        aria-label="Sign out"
        data-testid="sign-out"
        onClick={() => logout.mutate(undefined, { onSettled: () => router.push("/login") })}
      >
        <LogOut aria-hidden className="size-4" />
      </button>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  if (pathname.startsWith("/login")) {
    return (
      <>
        <DegradedBanner />
        <main id="main" className="flex-1">
          {children}
        </main>
      </>
    );
  }

  const onboarding = pathname.startsWith("/onboarding");

  return (
    <div className="flex min-h-dvh flex-col lg:flex-row">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-line bg-surface px-3 py-4 lg:sticky lg:top-0 lg:flex lg:h-dvh">
        <div className="px-3 pb-5">
          <Brand />
        </div>
        <nav aria-label="Main" className="flex-1" data-testid="sidebar-nav">
          {!onboarding && <NavLinks />}
        </nav>
        <UserBox />
      </aside>

      {/* Mobile top bar: the nav collapses into a menu button. */}
      <header className="sticky top-0 z-30 border-b border-line bg-surface lg:hidden">
        <div className="flex h-14 items-center justify-between px-4">
          <Brand />
          {!onboarding && (
            <button
              type="button"
              aria-expanded={open}
              aria-controls="mobile-nav"
              aria-label={open ? "Close menu" : "Open menu"}
              data-testid="nav-toggle"
              onClick={() => setOpen((o) => !o)}
              className="rounded-md p-2 hover:bg-subtle"
            >
              {open ? <X aria-hidden className="size-5" /> : <Menu aria-hidden className="size-5" />}
            </button>
          )}
        </div>
        {open && (
          <nav
            id="mobile-nav"
            aria-label="Main"
            data-testid="mobile-nav"
            className="border-t border-line px-3 py-3"
          >
            <NavLinks onNavigate={() => setOpen(false)} />
            <div className="mt-3">
              <UserBox />
            </div>
          </nav>
        )}
      </header>

      <div className="flex min-w-0 flex-1 flex-col">
        <DegradedBanner />
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
