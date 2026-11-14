import { ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";
import { Badge } from "./ui";

type Level = "low" | "medium" | "high";

const CONF: Record<Level, { tone: "green" | "amber" | "red"; label: string }> = {
  low: { tone: "green", label: "Low risk" },
  medium: { tone: "amber", label: "Medium risk" },
  high: { tone: "red", label: "High risk" },
};

export function levelFromScore(score: number): Level {
  return score >= 0.6 ? "high" : score >= 0.3 ? "medium" : "low";
}

/** Risk level with its score; the colour is never the only signal (icon + text). */
export function RiskBadge({
  level,
  score,
  flags,
}: {
  level?: Level | null;
  score?: number | null;
  flags?: string[];
}) {
  const lv = level ?? (score !== null && score !== undefined ? levelFromScore(score) : null);
  if (!lv) {
    return (
      <Badge tone="neutral" data-testid="risk-badge">
        <ShieldQuestion aria-hidden className="size-3.5" />
        Not assessed
      </Badge>
    );
  }
  const c = CONF[lv];
  const Icon = lv === "low" ? ShieldCheck : ShieldAlert;
  const title = flags?.length ? `Flags: ${flags.join(", ")}` : undefined;
  return (
    <Badge tone={c.tone} data-testid="risk-badge" data-level={lv} title={title}>
      <Icon aria-hidden className="size-3.5" />
      {c.label}
      {score !== null && score !== undefined && (
        <span className="tabular-nums opacity-75">· {Math.round(score * 100)}</span>
      )}
    </Badge>
  );
}

export function RecommendationBadge({ value }: { value?: "bid" | "watch" | "skip" | null }) {
  if (!value) return <Badge tone="neutral">Pending</Badge>;
  const tone = value === "bid" ? "accent" : value === "watch" ? "blue" : "neutral";
  return (
    <Badge tone={tone} data-testid="recommendation" data-value={value}>
      {value === "bid" ? "Bid" : value === "watch" ? "Watch" : "Skip"}
    </Badge>
  );
}
