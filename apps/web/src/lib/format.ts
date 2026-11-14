export function money(v: number | null | undefined, currency = "USD"): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: v % 1 === 0 ? 0 : 2,
  }).format(v);
}

export function price(v: number | null | undefined, rateType?: "hourly" | "fixed" | null) {
  if (v === null || v === undefined) return "—";
  return rateType === "hourly" ? `${money(v)}/hr` : money(v);
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function usd(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `$${v < 0.01 && v > 0 ? v.toFixed(4) : v.toFixed(v < 1 ? 3 : 2)}`;
}

export function seconds(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v < 1 ? `${Math.round(v * 1000)} ms` : `${v.toFixed(1)} s`;
}

const dateFmt = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

const timeFmt = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

export function dateTime(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : dateFmt.format(d);
}

export function clock(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : timeFmt.format(d);
}

export function humanize(s: string | null | undefined): string {
  if (!s) return "—";
  const t = s.replaceAll("_", " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
