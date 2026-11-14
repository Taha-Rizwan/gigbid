import { cx } from "@/lib/format";

export interface BarSeries {
  key: string;
  label: string;
  color: string; // tailwind bg-* class
  format?: (v: number) => string;
}

/**
 * Horizontal bar chart in plain CSS. Each row is labelled, values are printed
 * next to bars (colour is never the only carrier), and a visually hidden table
 * mirrors the data for screen readers.
 */
export function BarChart({
  rows,
  series,
  labelKey = "label",
  max,
  caption,
  scale = "shared",
}: {
  rows: Array<Record<string, unknown>>;
  series: BarSeries[];
  labelKey?: string;
  max?: number;
  caption: string;
  /** "per-series" scales each series to its own maximum (for mixed units). */
  scale?: "shared" | "per-series";
}) {
  const values = rows.flatMap((r) => series.map((s) => Number(r[s.key]) || 0));
  const shared = max ?? Math.max(1e-9, ...values);
  const topOf = (s: BarSeries) =>
    scale === "shared" ? shared : Math.max(1e-9, ...rows.map((r) => Number(r[s.key]) || 0));
  const fmt = (s: BarSeries, v: number) => (s.format ? s.format(v) : v.toLocaleString());

  return (
    <figure>
      {series.length > 1 && (
        <div className="mb-3 flex flex-wrap gap-4 text-xs text-muted" aria-hidden>
          {series.map((s) => (
            <span key={s.key} className="inline-flex items-center gap-1.5">
              <span className={cx("size-2.5 rounded-sm", s.color)} />
              {s.label}
            </span>
          ))}
        </div>
      )}
      <div className="space-y-3" aria-hidden>
        {rows.map((r, i) => (
          <div key={i}>
            <div className="mb-1 text-sm font-medium">{String(r[labelKey] ?? "—")}</div>
            <div className="space-y-1">
              {series.map((s) => {
                const v = Number(r[s.key]) || 0;
                return (
                  <div key={s.key} className="flex items-center gap-2">
                    <div className="h-3 flex-1 overflow-hidden rounded-sm bg-subtle">
                      <div className={cx("h-full rounded-sm", s.color)} style={{ width: `${(v / topOf(s)) * 100}%` }} />
                    </div>
                    <span className="w-16 shrink-0 text-right text-xs tabular-nums text-muted">{fmt(s, v)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <table className="sr-only">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">{labelKey}</th>
            {series.map((s) => (
              <th key={s.key} scope="col">
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <th scope="row">{String(r[labelKey] ?? "—")}</th>
              {series.map((s) => (
                <td key={s.key}>{fmt(s, Number(r[s.key]) || 0)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
