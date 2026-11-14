import type { components } from "@/lib/api/schema";

type S = components["schemas"];

export type UserOut = S["UserOut"];
export type ProfileIn = S["ProfileIn"];
export type ProfileOut = S["ProfileOut"];
export type Persona = ProfileIn["persona"];
export type Autonomy = ProfileIn["autonomy"];
export type ModelProfile = ProfileIn["model_profile"];
export type MarketplaceMode = ProfileIn["marketplace_mode"];
export type SavedSearch = S["SavedSearch"];
export type PortfolioItem = S["PortfolioItemOut"];
export type UploadResult = S["UploadResult"];
export type InboxItem = S["InboxItem"];
export type InboxOut = S["InboxOut"];
export type JobStatus = InboxItem["status"];
export type Recommendation = NonNullable<InboxItem["recommendation"]>;
export type JobDetail = S["JobDetail"];
export type JobSpec = S["JobSpec"];
export type RiskReport = S["RiskReport"];
export type FitReport = S["FitReport"];
export type RequirementMatch = S["RequirementMatch"];
export type PriceQuote = S["PriceQuote"];
export type EvidenceItem = S["EvidenceItem"];
export type Claim = S["Claim"];
export type ClaimLabel = S["ClaimLabel"];
export type Critique = S["Critique"];
export type ComplianceVerdict = S["ComplianceVerdict"];
export type ApprovalRequest = S["ApprovalRequest"];
export type ApprovalIn = S["ApprovalIn"];
export type ApprovalResult = S["ApprovalResult"];
export type RunStarted = S["RunStarted"];
export type StudioOut = S["StudioOut"];
export type ParagraphOut = S["ParagraphOut"];
export type PipelineCard = S["PipelineCard"];
export type Stage = PipelineCard["stage"];
export type ConversationSummary = S["ConversationSummary"];
export type ConversationOut = S["ConversationOut"];
export type MessageOut = S["MessageOut"];
export type RunOut = S["RunOut"];
export type RunEvent = S["RunEvent"];
export type RunStatus = RunOut["status"];
export type AnalyticsOut = S["AnalyticsOut"];
export type CategoryRate = S["CategoryRate"];
export type MemoryItem = S["MemoryItem"];
export type HealthOut = S["HealthOut"];

export const STAGES: Stage[] = [
  "drafted",
  "submitted",
  "viewed",
  "replied",
  "interview",
  "hired",
  "lost",
];

export const JOB_STATUSES: JobStatus[] = [
  "new",
  "analysing",
  "skipped",
  "watch",
  "drafting",
  "awaiting_approval",
  "submitted",
  "rejected",
  "needs_attention",
  "failed",
];

/**
 * `dry_run` is typed as a free-form object in the contract. This is the shape
 * GigSim returns from `POST /v1/proposals/drafts/{id}/submit?dry_run=true`
 * (docs/specs/GIGSIM_SPEC.md); every field is treated as optional.
 */
export interface DryRun {
  would_send?: {
    job_id?: string;
    cover_letter?: string;
    text?: string;
    screening_answers?: string[];
    bid_amount?: number;
    rate_type?: "hourly" | "fixed";
    [k: string]: unknown;
  };
  connects_cost?: number;
  balance_after?: number;
  policy_check?: { ok?: boolean; violations?: string[] };
  [k: string]: unknown;
}
