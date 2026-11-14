"use client";

import { useAnalytics } from "@/lib/hooks/queries";
import type { AnalyticsOut } from "@/lib/hooks/types";
import { humanize, pct, seconds, usd } from "@/lib/format";
import { Card, CardTitle, PageHeader, Stat } from "@/components/ui";
import { BarChart, type BarSeries } from "@/components/BarChart";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LoadingState } from "@/components/LoadingState";

const PALETTE = ["bg-accent", "bg-emerald-500", "bg-amber-500", "bg-sky-500", "bg-rose-500"];
const LABEL_KEYS = ["label", "week", "period", "date", "category", "bucket", "reason", "outcome", "name"];

/**
 * `connects_vs_outcomes` and `top_rejection_reasons` are untyped dicts in the
 * contract, so pick the label column and the numeric series from the data.
 */
function shape(rows: Array<Record<string, unknown>>) {
  const first = rows[0] ?? {};
  const labelKey =
    LABEL_KEYS.find((k) => typeof first[k] === "string") ??
    Object.keys(first).find((k) => typeof first[k] === "string") ??
    "label";
  const numeric = Object.keys(first).filter((k) => typeof first[k] === "number");
  return { labelKey, numeric };
}

export default function AnalyticsPage() {
  const analytics = useAnalytics();
  return (
    <>
      <PageHeader title="Analytics" description="What works: replies and hires by category, Connects spend, and what each proposal costs to produce." />
      {analytics.isPending ? (
        <LoadingState label="Crunching numbers" rows={4} />
      ) : analytics.isError ? (
        <ErrorState title="Could not load analytics" error={analytics.error} onRetry={() => analytics.refetch()} />
      ) : analytics.data.proposals_sent === 0 && analytics.data.jobs_analysed === 0 ? (
        <EmptyState title="No data yet" description="Analytics appear once GigBid has analysed jobs and you have sent proposals." />
      ) : (
        <Dashboard a={analytics.data} />
      )}
    </>
  );
}

function Dashboard({ a }: { a: AnalyticsOut }) {
  const cvo = shape(a.connects_vs_outcomes);
  const rej = shape(a.top_rejection_reasons);
  const cvoSeries: BarSeries[] = cvo.numeric.map((k, i) => ({ key: k, label: humanize(k), color: PALETTE[i % PALETTE.length] }));
  const rejKey = rej.numeric.find((k) => /count|n|total/i.test(k)) ?? rej.numeric[0];
  const byCat = a.by_category.map((c) => ({ ...c, label: c.category }));

  return (
    <div className="space-y-4" data-testid="analytics">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Proposals sent" value={a.proposals_sent} />
        <Stat label="Reply rate" value={pct(a.reply_rate)} />
        <Stat label="Hire rate" value={pct(a.hire_rate)} />
        <Stat label="Connects spent" value={a.connects_spent} />
        <Stat label="Cost per proposal" value={usd(a.cost_per_proposal_usd)} hint="LLM spend" />
        <Stat label="Latency p50" value={seconds(a.p50_latency_s)} hint="per proposal" />
        <Stat label="Latency p95" value={seconds(a.p95_latency_s)} hint="per proposal" />
        <Stat label="Scams flagged" value={a.scams_flagged} hint={`of ${a.jobs_analysed} jobs analysed`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle>Reply and hire rate by category</CardTitle>
          {byCat.length === 0 ? (
            <p className="text-sm text-muted">No proposals yet.</p>
          ) : (
            <BarChart
              caption="Reply and hire rate by category"
              rows={byCat}
              max={1}
              series={[
                { key: "reply_rate", label: "Reply rate", color: "bg-accent", format: (v) => pct(v) },
                { key: "hire_rate", label: "Hire rate", color: "bg-emerald-500", format: (v) => pct(v) },
              ]}
            />
          )}
        </Card>

        <Card>
          <CardTitle>Connects spent vs outcomes</CardTitle>
          {a.connects_vs_outcomes.length === 0 || cvoSeries.length === 0 ? (
            <p className="text-sm text-muted">No Connects spent yet.</p>
          ) : (
            <BarChart caption="Connects spent versus outcomes" rows={a.connects_vs_outcomes} labelKey={cvo.labelKey} series={cvoSeries} scale="per-series" />
          )}
          <p className="mt-3 text-xs text-muted">Each series is scaled to its own maximum; exact values are printed.</p>
        </Card>

        <Card>
          <CardTitle>Top rejection reasons</CardTitle>
          {a.top_rejection_reasons.length === 0 || !rejKey ? (
            <p className="text-sm text-muted">You have not rejected any drafts yet.</p>
          ) : (
            <BarChart
              caption="Top rejection reasons"
              rows={a.top_rejection_reasons}
              labelKey={rej.labelKey}
              series={[{ key: rejKey, label: humanize(rejKey), color: "bg-rose-500" }]}
            />
          )}
        </Card>

        <Card>
          <CardTitle>By category</CardTitle>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted">
                <tr>
                  <th scope="col" className="py-1.5 pr-2 font-medium">Category</th>
                  <th scope="col" className="py-1.5 pr-2 text-right font-medium">Sent</th>
                  <th scope="col" className="py-1.5 pr-2 text-right font-medium">Replies</th>
                  <th scope="col" className="py-1.5 text-right font-medium">Hires</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line tabular-nums">
                {a.by_category.map((c) => (
                  <tr key={c.category}>
                    <th scope="row" className="py-1.5 pr-2 text-left font-medium">{c.category}</th>
                    <td className="py-1.5 pr-2 text-right">{c.proposals}</td>
                    <td className="py-1.5 pr-2 text-right">{c.replies}</td>
                    <td className="py-1.5 text-right">{c.hires}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
