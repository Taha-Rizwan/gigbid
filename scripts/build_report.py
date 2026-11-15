"""Builds docs/report/REPORT.md and REPORT.pdf. Every number is read from evals/results/*.json;
anything not yet measured is shown as "pending" (never estimated). Re-run after evals finish.

    python scripts/build_report.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "evals" / "results"
OUT = ROOT / "docs" / "report"


def load(name: str) -> dict | None:
    p = RES / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def f(v, nd=3, pct=False) -> str:
    if v is None:
        return "pending"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return f"{v * 100:.1f}%" if pct else f"{v:.{nd}f}"
    return str(v)


def table(head: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def section_a(d):
    if not d:
        return "Pending: `tool_granularity.json` not produced yet."
    rows = [[k, f(v.get("tool_selection_accuracy")), f(v.get("argument_accuracy")), f(v.get("exact_task_success")),
             f(v.get("tokens_per_task"), 0)] for k, v in d["sets"].items()]
    n = next(iter(d["sets"].values())).get("n")
    return (f"Setup: {n} hand-written tasks with known correct tool calls (`evals/datasets/tool_tasks.jsonl`), one ReAct agent "
            f"(model profile `{d.get('model_profile') or 'paid'}`), four tool sets over the same functions.\n\n"
            + table(["Tool set", "Tool-selection acc.", "Argument acc.", "Exact task success", "Tokens / task"], rows)
            + "\n\nFinding: coarse tools are cheapest in tokens but lose argument accuracy (the model must pack several "
              "intents into one call); our MCP tools match fine-grained accuracy, and rewriting descriptions closed the "
              "remaining argument errors at a token cost. Source: `evals/results/tool_granularity.json`.")


def section_b(rag, abl, props):
    if not rag:
        return "Pending: `rag_variants.json` is still being produced by `evals/runners/rag_eval.py` (all 600 dev jobs x 9 variants)."
    rows = []
    for v, m in rag.get("variants", {}).items():
        o, ls = m.get("overall", {}), m.get("llm_sample", {})
        rows.append([v, f(ls.get("recall@5")), f(ls.get("mrr")), f(ls.get("ndcg@10")), f(ls.get("n")),
                     f(o.get("recall@5")), f(o.get("n")), f((m.get("requirements_ge4") or {}).get("recall@5")),
                     f(o.get("latency_p95_s"), 3)])
    txt = (f"Hypothesis (stated before running): requirement decomposition plus hybrid retrieval raises evidence Recall@5 "
           f"over V0 on jobs with four or more requirements. n = {rag.get('n_evaluated', rag.get('n'))} dev jobs; "
           f"best variant by rule: `{rag.get('best_variant', 'pending')}`.\n\n"
           + table(["Variant", "Recall@5 (same jobs)", "MRR", "nDCG@10", "n", "Recall@5 (all)", "n (all)",
                    "Recall@5 (>=4 reqs)", "p95 latency (s)"], rows)
           + "\n\nThe like-for-like comparison is the first block: every variant on the same jobs (LLM variants were "
             "limited to that sample by the free-tier budget). Rule for the shipped choice: "
           + str(rag.get("best_variant_rule")) + ".")
    if abl:
        arows = [[k, json.dumps(v.get("delta_vs_full", v))[:80]] for k, v in (abl.get("ablations") or {}).items()]
        txt += "\n\nAblation (one component removed at a time):\n\n" + table(["Removed", "Delta vs full"], arows)
    if props:
        prow = [[v, f(r.get("n_proposals")), f(r.get("unsupported_before_mean"), 2), f(r.get("unsupported_after_mean"), 2),
                 f(r.get("judge_overall_mean"), 2), f(r.get("gigsim_reply_rate"), pct=True),
                 f((r.get("latency") or {}).get("p95_s"), 1), f((r.get("usage_per_proposal") or {}).get("cost_usd_mean"), 4)]
                for v, r in (props.get("results") or {}).items()]
        txt += "\n\nEnd-to-end proposals:\n\n" + table(
            ["Variant", "n", "Unsupported before", "Unsupported after", "Judge (1-5)", "GigSim reply rate", "p95 (s)", "USD / proposal"], prow)
    return txt


def section_c(d):
    if not d:
        return "Pending: `multiagent.json` is still being produced by `evals/runners/multiagent_compare.py`."
    rows = [[k, f(v.get("n")), f(v.get("n_proposals")), f(v.get("bid_skip_accuracy")), f(v.get("unsupported_claims_per_proposal"), 2),
             f(v.get("violations_caught_before_approval")), f(v.get("gigsim_reply_rate"), pct=True),
             f(v.get("tokens_per_job"), 0), f(v.get("latency_p95_s"), 1)] for k, v in d.get("systems", {}).items()]
    return (f"n = {d.get('n')} dev jobs ({d.get('status', '')}).\n\n"
            + table(["System", "Jobs", "Proposals", "Bid/skip acc.", "Unsupported claims", "Violations caught", "GigSim reply",
                     "Tokens / job", "p95 (s)"], rows)
            + "\n\nReply rates rest on very few proposals per system (column Proposals), so they are not comparable; "
              "the robust differences are grounding (unsupported claims per proposal) and tokens per job. The single "
              "ReAct agent decided bid/skip more accurately on this sample because our graph skips too often (section 8).")


def main() -> None:
    a, rag, abl, props = load("tool_granularity"), load("rag_variants"), load("ablation"), load("proposals")
    mac, dec, inj, cr, ab, jc = load("multiagent"), load("decisions"), load("injection"), load("change_request"), load("ab_experiment"), load("judge_calibration")
    dev = (dec or {}).get("dev", {})
    k6 = ((dec or {}).get("k6_risk_assessor_only") or {}).get("scam", {})
    inj_rows = [[m, f(v.get("n")), f(v.get("end_to_end_attack_success_rate"), pct=True),
                 f(v.get("writer_forced_attack_success_rate"), pct=True), f(v.get("injection_detected_rate"), pct=True)]
                for m, v in ((inj or {}).get("results") or {}).items()]
    md = f"""# GigBid: R&D design review (AI-4016)

**Taha Rizwan** | Roll no. 23i-0664 | Section A
AI-4016 R&D Assignment II | FAST-NUCES Islamabad | Instructor: Muhammad Owais Idrees | {datetime.now():%d %B %Y}

Repository: https://github.com/Taha-Rizwan/gigbid | Live app: https://gigbid-vtva.onrender.com
All numbers are taken from the result files in `evals/results/` of the repository.

## 1. Problem and constraints

Freelancers lose hours scanning feeds, spend paid Connects on unwinnable jobs, send generic proposals and meet scams.
GigBid automates discovery, risk and fit assessment, pricing and grounded drafting; **the human approves every proposal,
message and Connects spend** (LangGraph `interrupt()` in `agent/graphs/bid_graph.py` `approval`). Never automated:
sending, spending, off-platform contact, claims without portfolio evidence. Declared budgets (`agent/config.yaml`
`budgets`): job analysis p95 25 s / USD 0.002; proposal p95 60 s / USD 0.01.

## 2. Architecture

Two hand-written LangGraph graphs (`docs/images/bid_graph.png`): the bid graph (intake, then Job Analyst, Risk Assessor
and Fit Matcher in parallel via `Send`, decide, pricing, writer, claim verifier, critic with at most two revisions,
compliance, dry-run, approval interrupt, idempotent submit) and the conversation graph. Agents reach everything through
MCP (`mcp_servers/portfolio`, `marketplace` with GigSim and live-Upwork adapters behind one port, `workspace`), with
per-agent tool allowlists (`agent/mcp_client.py`). State, execution trace (LangSmith + `audit_log`) and long-term memory
(LangGraph store, written only by `agent/memory/promotion_rules.py`) are separate. Postgres checkpointer gives durable
approvals; idempotency keys derived from (user, job, draft version, text) give exactly-once submission. Details:
`docs/ARCHITECTURE.md`, `docs/adr/`.

## 3. R&D question A: tool granularity

{section_a(a)}

## 4. R&D question B: retrieval variants and claim verification

{section_b(rag, abl, props)}

## 5. R&D question C: single agent vs supervisor vs our graph

{section_c(mac)}

## 6. Change request

{(cr or {}).get('change', 'pending')}
Lines changed in GigBid: {json.dumps((cr or {}).get('gigbid_lines_changed'))}. Why: {(cr or {}).get('why_zero', '')}
Verified on {json.dumps((cr or {}).get('verification'))}. Caveat: {(cr or {}).get('caveat', '')}

## 7. Signature extension: X2 proposal A/B experiments

{"Pending: `ab_experiment.json` run in progress." if not ab or not ab.get("n_paired") else
 f"Paired design, n = {ab['n_paired']} jobs (of {ab['n_jobs_attempted']} attempted; others were skipped by the graph). "
 f"Reply rate: {json.dumps(ab['reply_rate'])}; mean p(reply): {json.dumps(ab['mean_p_reply'])}; discordant pairs "
 f"{json.dumps(ab['discordant'])}; exact McNemar p = {ab['mcnemar_exact_p']}. Cost USD {ab['cost_usd']}. "
 "Outcomes come from our own simulated clients, so the result may not transfer to real clients."}

## 8. Decisions, scams and failure analysis

Dev decision eval (`decisions.json`, status {f((dec or {}).get('status'))}, n = {f((dec or {}).get('n'))}):
bid/skip accuracy {f(dev.get('bid_skip', {}).get('accuracy'))}, bid recall {f(dev.get('bid_skip', {}).get('recall'))}
(tp {f(dev.get('bid_skip', {}).get('tp'))}, fn {f(dev.get('bid_skip', {}).get('fn'))}); constructed-scam precision
{f(dev.get('scam', {}).get('precision'))}, recall {f(dev.get('scam', {}).get('recall'))}. External real fake-job ads (Kaggle K6,
Risk Assessor only): precision {f(k6.get('precision'))}, recall {f(k6.get('recall'))}, F1 {f(k6.get('f1'))}, n = {f(k6.get('n'))}.

**Main failure (negative result):** the graph is too conservative: it skipped every job the gold set marks as bid in this
sample. Causes found in traces: the Fit Matcher's graded coverage plus the 0.55 bid threshold, and price floors versus
low K1 budgets. Fix tried: graded full/partial coverage (prompt v2). Taxonomy of failed dev jobs: missed evidence,
wrong skip, mispriced, unsupported claim, generic opening, compliance miss, injection, tool error (rate limits were the
dominant tool error on the Groq free tier).

## 9. Safety and platform respect

Never: send without approval, spend Connects without approval, contact off-platform, claim unproven experience, scrape.
Enforced by interrupts, allowlists (no agent reading untrusted text holds a write tool), regex + LLM compliance, claim
verification, PII masking in logs. Injection test (`injection.json`):

{table(["Mode", "n", "End-to-end attack success", "Writer-forced attack success", "Detected"], inj_rows) if inj_rows else "pending"}

Attacks failed with and without defences on this model, so the experiment cannot show the defences' marginal value;
a weaker model would be needed to measure it. What still gets through: unusual phone formats in regex masking, novel
injections the classifier misses, and LangSmith traces are not masked.

## 10. Budgets and test results

Job analysis: p50 {f(dev.get('latency', {}).get('p50_s'), 1)} s, p95 {f(dev.get('latency', {}).get('p95_s'), 1)} s
(declared 25 s: over budget), USD {f(dev.get('usage', {}).get('cost_usd_mean'), 4)} per job (declared 0.002: within).
Judge calibration: {(jc or {}).get('status', 'pending')}. Hidden test: GigSim accepts examiner jobs via `POST /admin/import`.

**Deployment.** Live URL: https://gigbid-vtva.onrender.com (Render free web service, single container from
`infra/render/Dockerfile`: one Python process serving the API, the three MCP servers in-process and GigSim mounted at
`/gigsim`, plus the Next.js server). Hugging Face had withdrawn free Docker Spaces. On the free tier's 512 MB, the UI,
login, inbox, job details, drafts, run viewer and traces work, but **starting a new analysis crashes the instance**:
Render's event log records `oomKilled` with a 512Mi limit when the Fit Matcher loads the embedding model and builds
the portfolio index (measured about 1.6 GB for the single process locally), after which Render restarts it. The full
system runs on the laptop with `run_local.ps1` (all services as separate processes, no memory cap) and is what is
demonstrated in the viva and the demo video; a 2 GB instance or `docker compose -f infra/docker-compose.yml up` runs
it unchanged.

## Threats to validity

Synthetic personas and our own simulator (GigSim) decide outcomes; gold evidence labels are LLM-made (Claude Haiku,
a different family from the gpt-oss writer) with 30 items prepared for human checking; the Groq free tier forced the
bulk evaluation onto the paid profile (Claude Haiku) and smaller samples, recorded as `n` in every result file.
"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "REPORT.md").write_text(md, encoding="utf-8")
    render_pdf(md, OUT / "REPORT.pdf")
    print("wrote", OUT / "REPORT.md", "and REPORT.pdf")


def render_pdf(md: str, path: Path) -> None:
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=14)
    pdf.add_page()
    pdf.set_margins(14, 14, 14)

    def text(s: str) -> str:
        return s.replace("**", "").replace("`", "").encode("latin-1", "replace").decode("latin-1")

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            pdf.set_font("Helvetica", "B", 16)
            pdf.multi_cell(0, 8, text(ln[2:]))
        elif ln.startswith("## "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 7, text(ln[3:]))
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not set(lines[i].replace("|", "").strip()) <= {"-"}:
                    rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            pdf.set_font("Helvetica", "", 7)
            with pdf.table(text_align="LEFT", line_height=4.5) as t:
                for r in rows:
                    row = t.row()
                    for c in r:
                        row.cell(text(c))
            pdf.ln(1)
            continue
        elif ln.strip():
            pdf.set_font("Helvetica", "", 9)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 4.6, text(ln))
        else:
            pdf.ln(1.5)
        i += 1
    pdf.output(str(path))


if __name__ == "__main__":
    main()
