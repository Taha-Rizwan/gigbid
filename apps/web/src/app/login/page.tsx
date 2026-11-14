"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useLogin, useRegister } from "@/lib/hooks/queries";
import type { UserOut } from "@/lib/hooks/types";
import { Button, Field, Input } from "@/components/ui";
import { InlineError } from "@/components/ErrorState";
import { cx } from "@/lib/format";

type Tab = "signin" | "register";

function safeNext(): string | null {
  const next = new URLSearchParams(window.location.search).get("next");
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/login") ? next : null;
}

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();
  const register = useRegister();
  const pending = login.isPending || register.isPending;
  const error = tab === "signin" ? login.error : register.error;

  const go = (user: UserOut) => {
    router.replace(user.onboarded ? (safeNext() ?? "/inbox") : "/onboarding");
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (tab === "signin") login.mutate({ email, password }, { onSuccess: go });
    else register.mutate({ email, password, name }, { onSuccess: go });
  };

  return (
    <div className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div
            aria-hidden
            className="mx-auto mb-3 grid size-10 place-items-center rounded-lg bg-accent text-sm font-bold text-accent-fg"
          >
            GB
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">GigBid</h1>
          <p className="mt-1 text-sm text-muted">
            Your freelance copilot. It drafts; you decide what gets sent.
          </p>
        </div>

        <div className="rounded-lg border border-line bg-surface p-5">
          <div role="tablist" aria-label="Account" className="mb-5 grid grid-cols-2 gap-1 rounded-md bg-subtle p-1">
            {(["signin", "register"] as const).map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={tab === t}
                data-testid={`tab-${t}`}
                onClick={() => setTab(t)}
                className={cx(
                  "rounded px-3 py-1.5 text-sm font-medium",
                  tab === t ? "bg-surface shadow-sm" : "text-muted hover:text-fg",
                )}
              >
                {t === "signin" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4" data-testid="auth-form">
            {tab === "register" && (
              <Field label="Name" htmlFor="name">
                <Input
                  id="name"
                  data-testid="auth-name"
                  autoComplete="name"
                  required
                  maxLength={80}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </Field>
            )}
            <Field label="Email" htmlFor="email">
              <Input
                id="email"
                type="email"
                data-testid="auth-email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Field>
            <Field
              label="Password"
              htmlFor="password"
              hint={tab === "register" ? "At least 8 characters." : undefined}
            >
              <Input
                id="password"
                type="password"
                data-testid="auth-password"
                autoComplete={tab === "register" ? "new-password" : "current-password"}
                required
                minLength={tab === "register" ? 8 : undefined}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <InlineError error={error} />
            <Button type="submit" className="w-full" loading={pending} data-testid="auth-submit">
              {tab === "signin" ? "Sign in" : "Create account"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
