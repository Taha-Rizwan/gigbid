"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, ExternalLink } from "lucide-react";
import { useProfile, useSaveProfile } from "@/lib/hooks/queries";
import type { ProfileIn, ProfileOut } from "@/lib/hooks/types";
import { ApiError } from "@/lib/hooks/api";
import { PERSONAS, parseKeywords, toProfileIn } from "@/lib/profile";
import { Badge, Button, Card, Field, Input, PageHeader } from "@/components/ui";
import { ChoiceCards } from "@/components/ChoiceCards";
import { PortfolioUploader } from "@/components/PortfolioUploader";
import { SavedSearchesEditor } from "@/components/SavedSearchesEditor";
import { LoadingState } from "@/components/LoadingState";
import { ErrorState, InlineError } from "@/components/ErrorState";
import { cx } from "@/lib/format";

const STEPS = ["Persona", "Marketplace", "Portfolio", "Preferences"] as const;

export default function OnboardingPage() {
  const profile = useProfile();
  // A brand-new account may have no profile yet (404): start from defaults.
  const missing = profile.isError && profile.error instanceof ApiError && profile.error.status === 404;

  if (profile.isPending) return <LoadingState label="Loading your profile" rows={2} />;
  if (profile.isError && !missing) return <ErrorState error={profile.error} onRetry={() => profile.refetch()} />;
  return <Wizard initial={profile.data} />;
}

function Wizard({ initial }: { initial?: ProfileOut }) {
  const router = useRouter();
  const save = useSaveProfile();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<ProfileIn>(() => toProfileIn(initial));
  const [keywords, setKeywords] = useState((initial?.excluded_keywords ?? []).join(", "));
  const set = <K extends keyof ProfileIn>(k: K, v: ProfileIn[K]) => setForm((f) => ({ ...f, [k]: v }));

  const finish = () =>
    save.mutate(
      { ...form, excluded_keywords: parseKeywords(keywords) },
      { onSuccess: () => router.push("/inbox") },
    );

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Set up GigBid"
        description="Four quick steps. You can change all of this later in Settings."
      />

      <ol className="mb-6 grid grid-cols-4 gap-2" aria-label="Onboarding steps">
        {STEPS.map((s, i) => (
          <li key={s} aria-current={i === step ? "step" : undefined}>
            <div className={cx("h-1 rounded-full", i <= step ? "bg-accent" : "bg-line")} />
            <span className={cx("mt-1.5 block text-xs", i === step ? "font-semibold text-fg" : "text-muted")}>
              {i + 1}. {s}
            </span>
          </li>
        ))}
      </ol>

      <Card>
        {step === 0 && (
          <div className="space-y-4" data-testid="step-persona">
            <ChoiceCards
              name="persona"
              legend="Which profile should GigBid bid as?"
              value={form.persona}
              options={PERSONAS}
              onChange={(v) => set("persona", v)}
            />
            <Field label="Headline" htmlFor="display-title" hint="Shown at the top of your proposals. Optional.">
              <Input
                id="display-title"
                data-testid="display-title"
                placeholder="e.g. LLM engineer, 6 years shipping RAG systems"
                value={form.display_title ?? ""}
                onChange={(e) => set("display_title", e.target.value || null)}
              />
            </Field>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4" data-testid="step-marketplace">
            <ChoiceCards
              name="marketplace"
              legend="Where should GigBid look for work?"
              value={form.marketplace_mode}
              options={[
                {
                  value: "gigsim",
                  label: "GigSim (simulated marketplace)",
                  description: "Safe sandbox with realistic jobs, clients and replies. Recommended to start.",
                },
                {
                  value: "upwork_live",
                  label: "Upwork",
                  description: "Connect your Upwork account with OAuth. Proposals still need your approval.",
                },
              ]}
              onChange={(v) => set("marketplace_mode", v)}
            />
            {form.marketplace_mode === "upwork_live" && (
              <div className="flex flex-wrap items-center gap-3 rounded-md bg-subtle p-3 text-sm">
                {initial?.upwork_connected ? (
                  <Badge tone="green">
                    <Check aria-hidden className="size-3" /> Upwork connected
                  </Badge>
                ) : (
                  <>
                    <span>Not connected yet.</span>
                    {/* Full navigation: the backend redirects to Upwork's consent page. */}
                    <a
                      href="/api/oauth/upwork/start"
                      data-testid="connect-upwork"
                      className="inline-flex items-center gap-1 font-medium text-accent underline"
                    >
                      Connect Upwork <ExternalLink aria-hidden className="size-3.5" />
                    </a>
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {step === 2 && (
          <div data-testid="step-portfolio">
            <h2 className="mb-3 text-sm font-medium">Upload your portfolio evidence</h2>
            <PortfolioUploader />
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6" data-testid="step-preferences">
            <div className="grid gap-4 sm:grid-cols-3">
              <Field label="Hourly floor ($/hr)" htmlFor="hourly-floor">
                <Input
                  id="hourly-floor"
                  data-testid="hourly-floor"
                  type="number"
                  min={0}
                  value={form.hourly_floor}
                  onChange={(e) => set("hourly_floor", Number(e.target.value))}
                />
              </Field>
              <Field label="Fixed-price floor ($)" htmlFor="fixed-floor">
                <Input
                  id="fixed-floor"
                  data-testid="fixed-floor"
                  type="number"
                  min={0}
                  value={form.fixed_floor}
                  onChange={(e) => set("fixed_floor", Number(e.target.value))}
                />
              </Field>
              <Field label="Weekly Connects budget" htmlFor="connects-budget">
                <Input
                  id="connects-budget"
                  data-testid="connects-budget"
                  type="number"
                  min={0}
                  max={1000}
                  value={form.weekly_connects_budget}
                  onChange={(e) => set("weekly_connects_budget", Number(e.target.value))}
                />
              </Field>
            </div>
            <Field
              label="Excluded keywords"
              htmlFor="excluded"
              hint="Comma-separated. Jobs mentioning any of these are skipped (e.g. crypto, unpaid test)."
            >
              <Input
                id="excluded"
                data-testid="excluded-keywords"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
              />
            </Field>
            <div>
              <h2 className="mb-2 text-sm font-medium">Saved searches</h2>
              <SavedSearchesEditor />
            </div>
          </div>
        )}

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
          <Button variant="ghost" onClick={() => setStep((s) => s - 1)} disabled={step === 0}>
            <ArrowLeft aria-hidden className="size-4" /> Back
          </Button>
          {step < STEPS.length - 1 ? (
            <Button data-testid="onboarding-next" onClick={() => setStep((s) => s + 1)}>
              Next <ArrowRight aria-hidden className="size-4" />
            </Button>
          ) : (
            <Button data-testid="onboarding-finish" onClick={finish} loading={save.isPending}>
              Finish and open inbox
            </Button>
          )}
        </div>
        <div className="mt-2">
          <InlineError error={save.error} />
        </div>
      </Card>
    </div>
  );
}
