import type { Autonomy, ModelProfile, Persona, ProfileIn, ProfileOut } from "./hooks/types";

export const PERSONAS: Array<{ value: Persona; label: string; description: string }> = [
  { value: "ai_ml", label: "AI / ML engineer", description: "LLM apps, RAG, fine-tuning, ML pipelines." },
  { value: "fullstack", label: "Full-stack developer", description: "Web apps, APIs, dashboards, integrations." },
  { value: "data_analyst", label: "Data analyst", description: "SQL, BI dashboards, reporting, analysis." },
  { value: "own", label: "My own profile", description: "Describe yourself; GigBid uses your portfolio only." },
];

export const AUTONOMY: Array<{ value: Autonomy; label: string; description: string }> = [
  {
    value: "manual",
    label: "Manual",
    description: "GigBid ranks and drafts. You decide on every job and approve every message.",
  },
  {
    value: "auto_skip_low_fit",
    label: "Auto-skip low fit",
    description: "Jobs with low fit or high risk are skipped automatically, with the reason logged.",
  },
];

export const MODEL_PROFILES: Array<{ value: ModelProfile; label: string; description: string }> = [
  { value: "open", label: "Open models", description: "Default open-weight models." },
  { value: "open_alt", label: "Open (alternative)", description: "A second open-weight family for comparison." },
  { value: "paid", label: "Paid API", description: "Hosted frontier model. Higher cost per proposal." },
];

export const DEFAULT_PROFILE: ProfileIn = {
  persona: "ai_ml",
  display_title: null,
  hourly_floor: 35,
  fixed_floor: 150,
  weekly_connects_budget: 80,
  excluded_keywords: [],
  autonomy: "manual",
  marketplace_mode: "gigsim",
  model_profile: "open",
};

/** Strips the read-only fields from ProfileOut so it can be PUT back. */
export function toProfileIn(p: ProfileOut | ProfileIn | undefined): ProfileIn {
  if (!p) return { ...DEFAULT_PROFILE };
  return {
    persona: p.persona,
    display_title: p.display_title ?? null,
    hourly_floor: p.hourly_floor,
    fixed_floor: p.fixed_floor,
    weekly_connects_budget: p.weekly_connects_budget,
    excluded_keywords: p.excluded_keywords ?? [],
    autonomy: p.autonomy,
    marketplace_mode: p.marketplace_mode,
    model_profile: p.model_profile,
  };
}

export function parseKeywords(s: string): string[] {
  return s
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);
}
