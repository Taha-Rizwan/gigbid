"""Regenerate evals/results/tables.md purely from the JSON result files (no numbers typed by hand).

    python scripts/make_results_table.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "evals" / "results"
NA = "n/a"


def load(name: str) -> dict | None:
    p = RES / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def f(x, nd: int = 3, pct: bool = False) -> str:
    if x is None:
        return NA
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, int | float):
        return f"{x * 100:.1f}%" if pct else f"{x:.{nd}f}"
    return str(x)


def src(name: str, d: dict | None) -> str:
    if not d:
        return f"_Source: `evals/results/{name}` (missing: runner not run yet)._"
    return (f"_Source: `evals/results/{name}`, generated {d.get('generated_at')}, status **{d.get('status')}**, "
            f"n = {d.get('n')}, profile `{(d.get('config_snapshot') or {}).get('models', {}).get('profile')}`._")


def rag_table(rv: dict | None, props: dict | None) -> list[str]:
    out = ["## RAG variants (R&D question B)", "",
           "| Variant | Evidence Recall@5 | nDCG@10 | Unsupported claims/proposal | Judge score | GigSim reply rate | "
           "p95 latency (s) | Cost per proposal (USD) | n (retrieval / proposals) |",
           "|---|---|---|---|---|---|---|---|---|"]
    variants = (rv or {}).get("variants", {})
    pres = (props or {}).get("results", {})
    names = list(dict.fromkeys(list(variants) + list(pres)))
    for v in names:
        r = (variants.get(v) or {}).get("overall", {})
        p = pres.get(v) or {}
        lat = (p.get("latency") or {}).get("p95_s")
        cost = (p.get("usage_per_proposal") or {}).get("cost_usd_mean")
        out.append(f"| {v} | {f(r.get('recall@5'))} | {f(r.get('ndcg@10'))} | {f(p.get('unsupported_after_mean'), 2)} | "
                   f"{f(p.get('judge_overall_mean'), 2)} | {f(p.get('gigsim_reply_rate'), pct=True)} | {f(lat, 1)} | "
                   f"{f(cost, 4)} | {r.get('n', 0)} / {p.get('n_proposals', 0)} |")
    out += ["", "Retrieval columns: all labelled jobs the variant ran on (LLM-backed variants: a capped sample; see "
            "`llm_sample` in the JSON for the like-for-like subset). Proposal columns: proposal_eval, proposal-level "
            "p95 latency and cost; unsupported claims are after verification.", ""]
    if rv:
        out.append(f"Best variant by the rule `{rv.get('best_variant_rule')}`: **{rv.get('best_variant')}**.")
        ls = [(v, b.get("llm_sample", {})) for v, b in variants.items()]
        out += ["", "Like-for-like subset (`llm_sample`):", "", "| Variant | n | Recall@5 | MRR | nDCG@10 | p95 retrieval latency (s) |",
                "|---|---|---|---|---|---|"]
        out += [f"| {v} | {s.get('n', 0)} | {f(s.get('recall@5'))} | {f(s.get('mrr'))} | {f(s.get('ndcg@10'))} | "
                f"{f(s.get('latency_p95_s'), 4)} |" for v, s in ls]
        out += ["", "Jobs with >= 4 requirements:", "", "| Variant | n | Recall@5 | nDCG@10 |", "|---|---|---|---|"]
        out += [f"| {v} | {b.get('requirements_ge4', {}).get('n', 0)} | {f(b.get('requirements_ge4', {}).get('recall@5'))} | "
                f"{f(b.get('requirements_ge4', {}).get('ndcg@10'))} |" for v, b in variants.items()]
        for v, why in (rv.get("skipped") or {}).items():
            out.append(f"\n- {v}: {why}")
    out += ["", src("rag_variants.json", rv), src("proposals.json", props), ""]
    return out


def ablation_table(ab: dict | None) -> list[str]:
    out = ["## Ablation of the best pipeline", ""]
    if not ab or not ab.get("full"):
        return out + [src("ablation.json", ab), ""]
    out += [f"Pipeline: **{ab.get('best_variant')}** (n = {ab['full'].get('n')})", "",
            "| Setting | Recall@5 | MRR | nDCG@10 | delta Recall@5 | delta nDCG@10 |", "|---|---|---|---|---|---|",
            f"| full | {f(ab['full'].get('recall@5'))} | {f(ab['full'].get('mrr'))} | {f(ab['full'].get('ndcg@10'))} | | |"]
    for k, s in ab.get("ablations", {}).items():
        d = s.get("delta_vs_full", {})
        out.append(f"| {k} | {f(s.get('recall@5'))} | {f(s.get('mrr'))} | {f(s.get('ndcg@10'))} | "
                   f"{f(d.get('recall@5'))} | {f(d.get('ndcg@10'))} |")
    return out + ["", src("ablation.json", ab), ""]


def multiagent_table(ma: dict | None) -> list[str]:
    out = ["## Multi-agent comparison (R&D question C)", "",
           "| System | n | Bid/skip accuracy | Bid F1 | Scam recall | Unsupported claims/proposal | Violations left in output | "
           "Violations caught before approval | GigSim reply rate | Tokens/job | USD/job | p95 latency (s) |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s, r in ((ma or {}).get("systems") or {}).items():
        out.append(f"| {s} | {r.get('n', 0)} | {f(r.get('bid_skip_accuracy'), pct=True)} | {f(r.get('bid_f1'))} | "
                   f"{f(r.get('scam_recall'), pct=True)} | {f(r.get('unsupported_claims_per_proposal'), 2)} | "
                   f"{r.get('violations_left_in_output', NA)} | {r.get('violations_caught_before_approval', NA)} | "
                   f"{f(r.get('gigsim_reply_rate'), pct=True)} | {f(r.get('tokens_per_job'), 0)} | "
                   f"{f(r.get('cost_usd_per_job'), 4)} | {f(r.get('latency_p95_s'), 1)} |")
    if ma:
        out += ["", "By job type (bid/skip accuracy, n):", "", "| System | " + " | ".join(
            sorted({t for r in ma["systems"].values() for t in r.get("by_job_type", {})})) + " |"]
        types = sorted({t for r in ma["systems"].values() for t in r.get("by_job_type", {})})
        out.append("|---|" + "---|" * len(types))
        for s, r in ma["systems"].items():
            cells = [f"{f(r['by_job_type'].get(t, {}).get('bid_skip_accuracy'), pct=True)} ({r['by_job_type'].get(t, {}).get('n', 0)})"
                     for t in types]
            out.append(f"| {s} | " + " | ".join(cells) + " |")
    return out + ["", src("multiagent.json", ma), ""]


def decisions_table(d: dict | None) -> list[str]:
    out = ["## Decisions, scams and pricing", ""]
    if not d or not d.get("dev", {}).get("n"):
        return out + [src("decisions.json", d), ""]
    dev, k6 = d["dev"], d.get("k6_risk_assessor_only") or {}
    out += ["| Measure | Value | n |", "|---|---|---|",
            f"| Bid/skip F1 (bid = positive) | {f(dev['bid_skip'].get('f1'))} | {dev['n']} |",
            f"| Bid/skip accuracy | {f(dev['bid_skip'].get('accuracy'), pct=True)} | {dev['n']} |",
            f"| Scam precision / recall (dev) | {f(dev['scam'].get('precision'))} / {f(dev['scam'].get('recall'))} | {dev['n']} |",
            f"| Scam precision / recall (K6, Risk Assessor only) | {f((k6.get('scam') or {}).get('precision'))} / "
            f"{f((k6.get('scam') or {}).get('recall'))} | {k6.get('n', 0)} |",
            f"| Price inside fair band (bid jobs) | {f(dev['price'].get('inside_band_rate'), pct=True)} | {dev['price'].get('n_priced')} |",
            f"| Latency p50 / p95 (s) | {f(dev['latency'].get('p50_s'), 1)} / {f(dev['latency'].get('p95_s'), 1)} | {dev['latency'].get('n_cold')} |",
            f"| Tokens / USD per job | {f(dev['usage'].get('tokens_mean'), 0)} / {f(dev['usage'].get('cost_usd_mean'), 4)} | {dev['usage'].get('n')} |"]
    return out + ["", src("decisions.json", d), ""]


def tools_table(t: dict | None) -> list[str]:
    out = ["## Tool granularity (R&D question A)", "", "| Tool set | # tools | n tasks | Tool selection | Argument accuracy | "
           "Exact task success | Calls/task | Tokens/task |", "|---|---|---|---|---|---|---|---|"]
    for s, r in ((t or {}).get("sets") or {}).items():
        out.append(f"| {s} | {r.get('n_tools')} | {r.get('n', 0)} | {f(r.get('tool_selection_accuracy'), pct=True)} | "
                   f"{f(r.get('argument_accuracy'), pct=True)} | {f(r.get('exact_task_success'), pct=True)} | "
                   f"{f(r.get('calls_per_task'), 2)} | {f(r.get('tokens_per_task'), 0)} |")
    return out + ["", src("tool_granularity.json", t), ""]


def injection_table(i: dict | None) -> list[str]:
    out = ["## Prompt injection", "", "| Defences | n | End-to-end attack success | Reached approval | Attack success given drafted | "
           "Writer-forced attack success | Injection detected |", "|---|---|---|---|---|---|---|"]
    for m, r in ((i or {}).get("results") or {}).items():
        out.append(f"| {m} | {r.get('n', 0)} | {f(r.get('end_to_end_attack_success_rate'), pct=True)} | {r.get('n_reached_approval')} | "
                   f"{f(r.get('attack_success_given_drafted'), pct=True)} | {f(r.get('writer_forced_attack_success_rate'), pct=True)} "
                   f"(n={r.get('writer_forced_n')}) | {f(r.get('injection_detected_rate'), pct=True)} |")
    return out + ["", src("injection.json", i), ""]


def profiles_table(m: dict | None) -> list[str]:
    out = ["## Model profiles", "", "| Profile | Decisions n | Bid/skip accuracy | Bid F1 | Proposals n | Judge score | "
           "GigSim reply rate | p95 proposal latency (s) | USD/proposal | USD/job analysed |", "|---|---|---|---|---|---|---|---|---|---|"]
    for p, r in ((m or {}).get("profiles") or {}).items():
        d, pr = r.get("decisions") or {}, r.get("proposals") or {}
        out.append(f"| {p} | {d.get('n', 0)} | {f((d.get('bid_skip') or {}).get('accuracy'), pct=True)} | "
                   f"{f((d.get('bid_skip') or {}).get('f1'))} | {pr.get('n_proposals', 0)} | {f(pr.get('judge_overall_mean'), 2)} | "
                   f"{f(pr.get('gigsim_reply_rate'), pct=True)} | {f((pr.get('latency') or {}).get('p95_s'), 1)} | "
                   f"{f((pr.get('usage_per_proposal') or {}).get('cost_usd_mean'), 4)} | {f((d.get('usage') or {}).get('cost_usd_mean'), 4)} |")
    return out + ["", src("model_profiles.json", m), ""]


def judge_table(j: dict | None) -> list[str]:
    out = ["## Judge calibration", ""]
    if not j or j.get("status") == "awaiting_human_labels":
        return out + [f"Status: {(j or {}).get('status', 'missing')}. {(j or {}).get('reason', '')}", "", src("judge_calibration.json", j), ""]
    return out + [f"Cohen's kappa exact {f(j.get('kappa_exact'))}, quadratic-weighted {f(j.get('kappa_quadratic'))}, "
                  f"exact agreement {f(j.get('exact_agreement'), pct=True)} (n = {j.get('n')}).", "", src("judge_calibration.json", j), ""]


def main() -> int:
    md = ["# GigBid evaluation tables", "",
          "Generated by `scripts/make_results_table.py` from `evals/results/*.json`. Do not edit by hand.", ""]
    md += rag_table(load("rag_variants.json"), load("proposals.json"))
    md += ablation_table(load("ablation.json"))
    md += multiagent_table(load("multiagent.json"))
    md += decisions_table(load("decisions.json"))
    md += tools_table(load("tool_granularity.json"))
    md += injection_table(load("injection.json"))
    md += profiles_table(load("model_profiles.json"))
    md += judge_table(load("judge_calibration.json"))
    RES.mkdir(parents=True, exist_ok=True)
    (RES / "tables.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote {RES / 'tables.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
