"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { Ban, Check, ExternalLink, Link2Off } from "lucide-react";
import { useDisconnectUpwork, useProfile, useSaveProfile } from "@/lib/hooks/queries";
import type { ProfileIn, ProfileOut } from "@/lib/hooks/types";
import { AUTONOMY, MODEL_PROFILES, PERSONAS, parseKeywords, toProfileIn } from "@/lib/profile";
import { Badge, Button, Card, CardTitle, Field, Input, PageHeader } from "@/components/ui";
import { ChoiceCards } from "@/components/ChoiceCards";
import { SavedSearchesEditor } from "@/components/SavedSearchesEditor";
import { MemoryViewer } from "@/components/MemoryViewer";
import { PortfolioUploader } from "@/components/PortfolioUploader";
import { ErrorState, InlineError } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";

export default function SettingsPage() {
  const profile = useProfile();
  return (
    <>
      <PageHeader title="Settings" description="How much GigBid may do on its own, what it may spend, and what it has learned." />
      {profile.isPending ? (
        <LoadingState label="Loading settings" rows={4} />
      ) : profile.isError ? (
        <ErrorState title="Could not load your settings" error={profile.error} onRetry={() => profile.refetch()} />
      ) : (
        <div className="space-y-6">
          <ProfileForm profile={profile.data} />
          <Section title="Saved searches" description="The scout runs these on their interval.">
            <SavedSearchesEditor />
          </Section>
          <Section title="Connected accounts">
            <Accounts profile={profile.data} />
          </Section>
          <Section title="Portfolio">
            <PortfolioUploader />
          </Section>
          <Section title="Memory" description="What GigBid has learned from your decisions. Forget anything you do not want it to use.">
            <MemoryViewer />
          </Section>
        </div>
      )}
    </>
  );
}

function Section({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <Card>
      <CardTitle>{title}</CardTitle>
      {description && <p className="-mt-2 mb-4 text-sm text-muted">{description}</p>}
      {children}
    </Card>
  );
}

function ProfileForm({ profile }: { profile: ProfileOut }) {
  const save = useSaveProfile();
  const [form, setForm] = useState<ProfileIn>(() => toProfileIn(profile));
  const [keywords, setKeywords] = useState((profile.excluded_keywords ?? []).join(", "));
  const [saved, setSaved] = useState(false);
  const set = <K extends keyof ProfileIn>(k: K, v: ProfileIn[K]) => {
    setSaved(false);
    setForm((f) => ({ ...f, [k]: v }));
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate({ ...form, excluded_keywords: parseKeywords(keywords) }, { onSuccess: () => setSaved(true) });
  };

  const used = profile.connects_spent_this_week;
  const budget = form.weekly_connects_budget;

  return (
    <form onSubmit={submit} className="space-y-6" data-testid="settings-form">
      <Section title="Autonomy">
        <ChoiceCards name="autonomy" legend="What may GigBid do without asking?" value={form.autonomy} options={AUTONOMY} onChange={(v) => set("autonomy", v)} />
        <p className="mt-3 flex items-start gap-2 rounded-md bg-subtle p-3 text-sm" data-testid="no-auto-send">
          <Ban aria-hidden className="mt-0.5 size-4 shrink-0 text-red-600 dark:text-red-400" />
          <span>
            <strong>Auto-send is never allowed.</strong> Every proposal and every client message waits for your
            explicit approval, whatever the autonomy level.
          </span>
        </p>
      </Section>

      <Section title="Budgets and floors">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Weekly Connects budget" htmlFor="s-connects" hint={`${used} spent this week${profile.connects_balance != null ? ` · balance ${profile.connects_balance}` : ""}`}>
            <Input id="s-connects" data-testid="settings-connects-budget" type="number" min={0} max={1000} value={budget} onChange={(e) => set("weekly_connects_budget", Number(e.target.value))} />
          </Field>
          <Field label="Hourly floor ($/hr)" htmlFor="s-hourly">
            <Input id="s-hourly" type="number" min={0} value={form.hourly_floor} onChange={(e) => set("hourly_floor", Number(e.target.value))} />
          </Field>
          <Field label="Fixed-price floor ($)" htmlFor="s-fixed">
            <Input id="s-fixed" type="number" min={0} value={form.fixed_floor} onChange={(e) => set("fixed_floor", Number(e.target.value))} />
          </Field>
        </div>
        {budget > 0 && (
          <div className="mt-3">
            <div className="mb-1 flex justify-between text-xs text-muted">
              <span>Connects used this week</span>
              <span className="tabular-nums">
                {used}/{budget}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-subtle" aria-hidden>
              <div className={used > budget ? "h-full bg-red-500" : "h-full bg-accent"} style={{ width: `${Math.min(100, (used / budget) * 100)}%` }} />
            </div>
          </div>
        )}
        <Field className="mt-4" label="Excluded keywords" htmlFor="s-excluded" hint="Comma-separated.">
          <Input id="s-excluded" value={keywords} onChange={(e) => { setSaved(false); setKeywords(e.target.value); }} />
        </Field>
      </Section>

      <Section title="Profile and model">
        <div className="space-y-5">
          <ChoiceCards name="s-persona" legend="Persona" value={form.persona} options={PERSONAS} onChange={(v) => set("persona", v)} columns={4} />
          <Field label="Headline" htmlFor="s-title">
            <Input id="s-title" value={form.display_title ?? ""} onChange={(e) => set("display_title", e.target.value || null)} />
          </Field>
          <ChoiceCards name="model" legend="Model profile" value={form.model_profile} options={MODEL_PROFILES} onChange={(v) => set("model_profile", v)} columns={3} />
          <ChoiceCards
            name="s-marketplace"
            legend="Marketplace"
            value={form.marketplace_mode}
            options={[
              { value: "gigsim", label: "GigSim", description: "Simulated marketplace." },
              { value: "upwork_live", label: "Upwork", description: "Requires a connected Upwork account." },
            ]}
            onChange={(v) => set("marketplace_mode", v)}
          />
        </div>
      </Section>

      <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center gap-3 border-t border-line bg-bg/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-lg sm:border">
        <Button type="submit" data-testid="settings-save" loading={save.isPending}>
          Save settings
        </Button>
        {saved && (
          <span role="status" className="inline-flex items-center gap-1 text-sm text-emerald-700 dark:text-emerald-300">
            <Check aria-hidden className="size-4" /> Saved
          </span>
        )}
        <InlineError error={save.error} />
      </div>
    </form>
  );
}

function Accounts({ profile }: { profile: ProfileOut }) {
  const disconnect = useDisconnectUpwork();
  return (
    <ul className="divide-y divide-line rounded-lg border border-line">
      <li className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <div className="font-medium">GigSim</div>
          <div className="text-sm text-muted">Simulated marketplace, always available.</div>
        </div>
        <Badge tone={profile.marketplace_mode === "gigsim" ? "green" : "neutral"}>
          {profile.marketplace_mode === "gigsim" ? "Active" : "Available"}
        </Badge>
      </li>
      <li className="flex flex-wrap items-center justify-between gap-3 p-4" data-testid="upwork-account">
        <div>
          <div className="font-medium">Upwork</div>
          <div className="text-sm text-muted">
            {profile.upwork_connected ? "Connected with OAuth." : "Not connected."}
          </div>
        </div>
        {profile.upwork_connected ? (
          <Button variant="danger" size="sm" data-testid="disconnect-upwork" loading={disconnect.isPending} onClick={() => disconnect.mutate()}>
            <Link2Off aria-hidden className="size-3.5" /> Disconnect
          </Button>
        ) : (
          <a href="/api/oauth/upwork/start" data-testid="connect-upwork" className="inline-flex h-8 items-center gap-1 rounded-md border border-line px-2.5 text-sm font-medium hover:bg-subtle">
            Connect <ExternalLink aria-hidden className="size-3.5" />
          </a>
        )}
      </li>
      {disconnect.isError && (
        <li className="p-3">
          <InlineError error={disconnect.error} />
        </li>
      )}
    </ul>
  );
}
