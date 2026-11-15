# GigBid data card

This card covers every dataset GigBid uses: what is real and what is synthetic, where each piece
came from, how it was processed, and what it should not be used for. Everything listed here is
rebuilt by `make seed` (see "Rebuild" at the end). The numbers come from
`data/processed/build_stats.json` and `scripts/validate_data.py` for the build described here.

## 1. Sources and licences

| Key | Kaggle dataset | Licence | Used for | Committed? |
|---|---|---|---|---|
| K1 | `asaniczka/upwork-job-postings-dataset-2024-50k-records` (`upwork-jobs.csv`) | ODC-By 1.0 | GigSim job corpus, dev / held-out jobs, contexts for past proposals | Derived eval sets only (`evals/datasets/dev_*.jsonl`) |
| K2 | `asaniczka/all-jobs-on-upwork-200k-plus` (3 CSVs, no descriptions) | ODC-By 1.0 | Posted-price statistics per category | No (aggregates only) |
| K3 | `ahmedmyalo/upwork-freelance-jobs-60k` (`Final_Upwork_Dataset.csv`) | Apache-2.0 | Skill-tag gold labels, OOD held-out slice | `evals/datasets/k3_skills_eval.jsonl` |
| K4 | `asaniczka/freelance-contracts-dataset-1-3-million-entries` (`contracts.csv`) | ODC-By 1.0 | Realised hourly rates (fair price band). **Aggregate use only.** | No (aggregates only) |
| K5 | `sarveshchhetri/freelancer-success-earnings-and-churn-prediction` (12k synthetic rows) | Apache-2.0 | GigSim competitor-quality distribution | No (21 quantiles only) |
| K6 | `adityammantri/trial-1` (fake job-posting detection, `processed_labeled_dataset_without_encoding.xlsx`) | **Unknown** | Risk Assessor external eval only | **Never.** It lives in `data/processed/k6_scam_eval.jsonl`, which is gitignored |

**Attribution lines** (include them wherever derived data is shown or redistributed):

- "Contains information from *Upwork Job Postings Dataset 2024 (50k records)*, *All Jobs on Upwork
  (200k+)* and *Freelance Contracts Dataset (1.3 million entries)* by asaniczka on Kaggle, made
  available under the Open Data Commons Attribution License (ODC-By) v1.0."
- "Contains data from *Upwork Freelance Jobs 60k* by ahmedmyalo on Kaggle, licensed under Apache-2.0."
- "Contains data from *Freelancer Success, Earnings and Churn Prediction* by sarveshchhetri on Kaggle,
  licensed under Apache-2.0."
- K6 has no stated licence. We use it only locally, as an external evaluation set, and never
  redistribute it.

Raw downloads go to `data/raw/<key>/` via `scripts/download_kaggle.py`, which uses the Kaggle REST
API with `KAGGLE_API_TOKEN` (Bearer). They are gitignored.

## 2. Real vs synthetic boundary

| Artefact | Real | Synthetic |
|---|---|---|
| Job titles / descriptions / prices / countries / dates (K1, K3) | yes | - |
| Scam and injection paragraphs inserted into ~8% of GigSim jobs and ~10% of dev jobs | - | yes, templated (`source: kaggle_k1_modified`) |
| Reposts with `source: synthetic_repost` (100) | copied from real jobs | title prefix + new id/date |
| Natural reposts (`duplicate_of` on `kaggle_k1` rows) | yes, K1 near-duplicates | - |
| GigSim clients (names, history, reviews, hidden prefs) | - | yes, sampled per job (`synthetic: true`) |
| GigSim `skills[]`, `screening_questions[]`, `proposals_count`, `experience_level` for K1 jobs | - | rule-based (taxonomy lexicon / templates / lognormal draws); K3 experience levels are real |
| Market stats, competitor quantiles | aggregates of real (K1/K2/K4) and synthetic (K5) rows | - |
| Personas: profiles, CVs, case studies, repos, reviews | - | yes, LLM-generated from the hand-written `scripts/persona_specs.yaml` |
| Past proposals | the job they answer is real K1 | the letter is LLM-written; the outcome comes from GigSim's simulated client model |
| Gold labels | `is_scam`/`has_injection` by construction; fair price from real K4 | evidence, requirements, skills and hours from an LLM labeller |

Every synthetic record carries `synthetic: true` and a `generator: {model, prompt_version, seed}`
field (case-study front matter, `profile.json`, `reviews.jsonl`, `proposals.jsonl`, repo
`.evidence.json`). The personas, their employers and clients are fictional. Any resemblance to real
companies is unintended.

## 3. Row counts, splits and LLM usage

### Rows before and after each step

| Step | Rows |
|---|---|
| K1 raw | 53,058 |
| K1 job id parsed from link | 53,058 (100%) |
| K1 after dropping empty title/description and bad dates | 53,058 |
| K1 exact duplicate ids removed | 81, leaving **52,977** clean rows |
| K1 near-duplicates (reposts) flagged, kept | 2,090 |
| K1 by window | dev (11–19 Feb) 35,132; held-out (20–23 Feb) 17,703; earlier 142 |
| K1 eligible pools (original, ≥250-char description, priced) | dev 27,971; held-out 14,030 |
| K2 raw (3 CSVs) → id-dedup → not already in K1 | 826,328 → 731,485 → 679,033 |
| Posted-price rows used (K1+K2) | hourly 301,447; fixed 311,698 |
| K4 raw → with rate > 0 → within 3–250 USD/h → after per-category Tukey | 1,292,791 → 493,416 → 491,119 → **458,313** |
| K3 raw → id-dedup, ≥200-char description | 63,950 → 46,659 (0 ids overlap K1) |
| K5 | 12,000 → 21 competitor-quality quantiles |
| K6 raw → labelled, ≥150 chars, text-dedup → eval sample | 54,391 → 26,145 → 400 (200 fake / 200 real) |

K1 categories: other 9,785; marketing 8,320; design_3d 7,789; web_fullstack 5,831; writing 5,752;
video_audio 3,698; admin_support 2,432; ecommerce 1,929; data_analysis 1,643; mobile 1,531;
finance_accounting 1,501; automation_scraping 1,227; ml_ai 744; devops_cloud 656; data_engineering 139.

### Outputs

| File | Rows | Notes |
|---|---|---|
| `data/personas/<p>/case_studies/` | 19 / 19 / 19 | ai_ml / fullstack / data_analyst |
| `data/personas/<p>/repos/` | 5 / 5 / 5 | 2 vague READMEs each |
| `data/personas/<p>/reviews.jsonl` | 14 / 13 / 12 | |
| `data/personas/<p>/proposals.jsonl` | **134 / 60 / 60** of 150 planned each | see "Incomplete" below |
| `data/personas/<p>/index.jsonl` | every evidence item | catalogue for RAG and the labeller (an addition to the spec) |
| `evals/datasets/dev_<p>.jsonl` | 200 each | 100 core / 60 adjacent / 40 unrelated; 13 scams + 7 injections; gold bid = 27 / 18 / 31 |
| `data/processed/heldout_jobs.jsonl` | 150 | 40 K1 + 10 K3 per persona; gold bid = 19 |
| `evals/datasets/human_check.jsonl` | 30 | 10 per persona, gold empty |
| `evals/datasets/k3_skills_eval.jsonl` | 150 | |
| `data/processed/k6_scam_eval.jsonl` | 400 | never committed |
| `data/processed/gigsim_seed/jobs.jsonl` | 7,120 | 382 scams + 182 injections (7.9%); 220 reposts (120 natural, 100 synthetic); 2,812 open at start |
| `data/processed/gigsim_seed/clients.jsonl` | 6,096 | 881 clients post >1 seed job; 381 scammers |
| `data/processed/gigsim_seed/accounts.jsonl` | 3 | `acct_ai`, `acct_web`, `acct_data` |

**Gold bid rates are low (9–16%), and mostly because of price.** `below_floor` drives most skips.
K1's posted rates (hourly P50 ≈ 22.5 USD/h) sit well below the persona floors (40 / 35 / 28 USD/h).
That is a property of the real market data, not a labelling error. If a more balanced bid/skip set
is wanted, lower `floor_rate` in `scripts/persona_specs.yaml` and rerun
`scripts/build_dataset.py --relabel-only`; the cached labels make that free.

**Past-proposal outcomes** (GigSim scorer):
- ai_ml: 9 won / 5 replied / 120 ignored. Won rate by style: specific 12%, generic 0%, short 0%.
- fullstack: 2 won / 58 ignored.
- data_analyst: 3 won / 1 replied / 56 ignored.

### Incomplete: past proposals (196 of 450 missing)

- **Generic and short proposals are complete:** 114 per persona, all from templates.
- **Specific and long proposals** must be written by `gpt-oss-120b` or `gpt-oss-20b`. Both hit
  Groq's 200k-tokens/day free-tier cap. The cap is shared with other agents using the same key.
- Done so far: ai_ml has all 68 specific and 6 of 22 long proposals; fullstack and data_analyst
  have 1 specific and 1 long each.
- Rerunning `scripts/label_proposals.py` after the caps roll over fills the gaps from the cache.
  Evidence ids are fixed over the full plan, so existing `…:proposal:NNN` ids do not change.

### LLM token usage (every fresh call, from `data/cache/llm_spend.jsonl`)

| Model | Calls | Prompt tokens | Completion tokens | Total |
|---|---|---|---|---|
| `openai/gpt-oss-120b` (personas, proposals) | 111 | 89,119 | 99,630 | 188,749 |
| `openai/gpt-oss-20b` (fallback: proposals, 1 case study) | 49 | 92,086 | 38,227 | 130,313 |
| `qwen/qwen3.8-27b` (gold labels, 4 case studies) | 46 | 130,296 | 20,025 | 150,321 |
| `claude-haiku-5-5` (gold labels) | 119 | 617,278 | 180,312 | 797,590 |
| **Total** | 325 | 928,779 | 338,194 | **1,266,973** |

- Claude Haiku cost: **$0.15** at $0.10 / $0.50 per 1M tokens.
- Groq usage was free-tier.
- The totals include retried outputs that failed validation.
- A rebuild with the current cache costs 0 tokens.

## 4. Processing steps (`scripts/build_dataset.py` → `rag/ingest/dataset.py`)

1. **K1 cleaning.** `job_id` is the `~01…` id in the URL-decoded `link` (every row has one). HTML
   entities are unescaped, and the source's lost apostrophes (`We�re`) are repaired. Rows with an
   empty title or description, or an unparseable date, are dropped. Exact duplicate ids are removed
   (first by date kept). **Near-duplicates** (same normalised title + first 300 description
   characters, different id) are flagged with `near_dup_of`/`is_near_dup` and kept, because they are
   real reposts. `is_hourly` is normalised, and when missing it is inferred from which price fields
   are set. Prices ≤ 0 become null. Each row gets a taxonomy `category`, `category_score`, rule-based
   `skills[]` (lexicon in `data/taxonomy.yaml`), and a `window` (`dev` 11–19 Feb, `heldout` 20–23 Feb,
   `pre` earlier).
2. **Market stats** (`data/processed/market_stats.json`, also copied into the GigSim seed).
   - *Posted* hourly (midpoint of low/high, kept within 3–300 USD/h) and fixed budgets (5–50,000 USD) come
     from K1 plus K2. K2 rows whose id is already in K1 are dropped, and K2 is categorised by title only.
   - *Realised* hourly comes from K4 `hourly_rate`: rows with a rate > 0 are kept, then a hard
     3–250 USD/h bound, then per-category Tukey fences (1.5×IQR). K4 is categorised by `job_title`.
   - Each block is `{p25, p50, p75, n}` per category, plus `_all`.
3. **Competitor quality** (`competitors.json`). For each K5 freelancer: composite = 0.45·success_score
   + 0.25·job_success_rate + 0.15·profile_completeness + 0.15·has_portfolio. This is scaled from its
   P1–P99 range into 0.15–0.90 (the proposal-quality scale GigSim uses), and we keep 21 quantiles.
4. **Splits.** Eligible jobs: originals only, description ≥ 250 chars, priced, `is_hourly` known.
   The dev set comes from the dev window and the held-out set from the held-out window plus K3 (K3 ids
   that also appear in K1 are removed). Each persona's mix is 50/30/20 core/adjacent/unrelated. Sets are
   disjoint across personas and splits.
   - **Past-proposal jobs** come from K1 before 20 Feb: not in any eval set, not a near-duplicate of
     one, and 70/25/5 core/adjacent/other.
   - **K3 skills eval:** 150 more K3 jobs with ≥ 3 tags, round-robin across categories.
   - **K6 eval:** 200 fake + 200 real labelled posts with ≥ 150 chars of text, deduplicated on text.
5. **Scam / injection construction.** A templated paragraph is appended to (or, for injections,
   sometimes inserted mid-way into) a real description.
   - Scam types: off-platform contact, payment from the freelancer, credential/ID requests, unpaid
     trial, budget mismatch (which also rewrites the price).
   - Injections: five templates addressed to "AI assistants / automated tools".
   - Flags: `is_scam` / `has_injection`, `scam_type`, `source: kaggle_k1_modified`.
6. **GigSim seed** (`data/processed/gigsim_seed/`).
   - Jobs: every dev, held-out and past-proposal job, plus extra K1 jobs. About 30% are open at start
     (published in the 2 days before `GIGSIM_START = 2024-02-20T09:00Z`); the rest form the live
     stream (`release_minute > 0`).
   - `release_minute` = minutes between `published_date` and `GIGSIM_START`. Past-proposal and dev jobs
     are therefore old, already-released jobs. K3 jobs get a random positive minute.
   - Extra jobs are corrupted until ~8% of the seed is scam or injection.
   - Reposts: natural K1 near-duplicates whose original is in the seed, plus 100 synthetic reposts
     (title prefix, +12–60 h, `duplicate_of`).
   - Clients: one per job. ~12% of non-scam jobs reuse an existing client in the same category,
     reposts reuse the original's client, and scam jobs always get their own `is_scammer` client.
   - Client hidden prefs: `must_have_skills` (2–3 of the job's skills, topped up from category
     defaults), `budget_ceiling_factor` U(0.85, 1.35), `dislikes_generic` p=0.6, `max_words` ∈
     {120…350}, `prefers_questions` p=0.4, and `responsiveness` ~ Beta(2.2, 2.0) clipped to 0.1–0.95.
   - Accounts are the three personas (`acct_ai` / `acct_web` / `acct_data`, tokens
     `gigsim-token-{ai,web,data}`, 2,000 Connects, 400 weekly).
7. **Gold labels** for dev and held-out, using `qwen/qwen3.8-27b` then `claude-haiku-5-5` (see section 3); the rules are in
   `evals/datasets/LABELING.md`.

## 5. Taxonomy (`data/taxonomy.yaml`)

Fifteen categories. Each has case-insensitive whole-word keyword rules, scored as
3 × distinct title hits + min(4, distinct description hits). The winner needs a score ≥ 2, ties go to
the earlier category, and anything else is `other`. The `description` is for embedding fallback.

| Category | Description | # keyword rules |
|---|---|---|
| `ml_ai` | Machine learning, AI and LLM work: model training, NLP, computer vision, chatbots, RAG, AI agents, prompt engineering. | 51 |
| `data_engineering` | Data pipelines, ETL/ELT, data warehouses, orchestration, streaming and database engineering. | 22 |
| `data_analysis` | Data analysis, BI dashboards, reporting, statistics, spreadsheets and visualisation. | 27 |
| `web_fullstack` | Web application development: front end, back end, full stack, APIs, SaaS products, web frameworks. | 38 |
| `mobile` | Mobile app development for iOS and Android, cross-platform frameworks. | 14 |
| `ecommerce` | E-commerce store setup and management: Shopify, WooCommerce, Amazon and marketplace listings. | 17 |
| `devops_cloud` | DevOps, cloud infrastructure, CI/CD, containers, Linux administration and security. | 24 |
| `automation_scraping` | Web scraping, crawling, bots and workflow automation (Zapier, Make, n8n, RPA, browser automation). | 21 |
| `design_3d` | Graphic, UI/UX, brand, illustration, 3D modelling, CAD and animation design work. | 29 |
| `video_audio` | Video editing, motion graphics, audio, voice-over, podcast and music production. | 19 |
| `marketing` | Digital marketing, SEO, paid ads, social media management, email marketing, lead generation and sales. | 30 |
| `writing` | Content writing, copywriting, blogging, editing, proofreading, technical writing and translation. | 19 |
| `finance_accounting` | Bookkeeping, accounting, tax, financial analysis, payroll and legal/compliance support. | 18 |
| `admin_support` | Virtual assistance, data entry, customer support, project management and research tasks. | 18 |
| `other` | Everything else (engineering, education, games, hardware, consulting, ...). | 0 |

The file also has a 110-entry **skill lexicon** (canonical skill → regex alternatives) and the
persona → core/adjacent category map.

## 6. Synthetic generation

All generation goes through `rag/ingest/llm.py`.
- It calls Groq's OpenAI-compatible endpoint with `GROQ_API_KEY` from `.env` (never logged).
- Every response is cached in `data/cache/llm/<sha256 of the request>.json`.
- On a 429 it backs off using `retry-after`, with 3 concurrent requests per model.
- An output validator rejects bad generations (they are retried and never cached).
- Every fresh call is appended to `data/cache/llm_spend.jsonl` for the token totals below.

**Personas** (`scripts/build_personas.py`, prompt version `persona_v1`).
- Source: the hand-written `scripts/persona_specs.yaml`. Each persona has a name, rate, floor rate,
  employers with dates, 8–9 projects (exact stack, "implied" phrasing, outcome numbers) and 11 minor gigs.
- The three personas share a small world: Brightcart, Keystone Realty and Cargoline Freight appear in
  more than one history, and pandas overlaps between ai_ml and data_analyst.
- Generator: `openai/gpt-oss-120b` with `reasoning_effort: low`.
- One call per case study, repo and CV, and one call per persona for all its reviews.
- **Exception:** 5 short gig case studies failed the tightened 250-word minimum after `gpt-oss-120b`
  hit its daily cap. They were regenerated by the fallback chain: 1 by `openai/gpt-oss-20b` and 4 by
  `qwen/qwen3.8-27b` (fullstack `core-web-vitals-rescue`, `marketplace-payouts-fix`; data_analyst
  `looker-studio-ads-report`, `wix-site-update`). Each file's `generator.model` records which model
  wrote it.

Messiness is designed in:
- Case studies may name at most two stack tools, which the validator enforces; other skills are only
  implied ("scheduled nightly loads with retries and backfills" for Airflow).
- Reviews are in the client's voice and avoid tool names.
- Each persona has 2 repos whose README is deliberately vague (one of six stock vague READMEs) while
  the code is clear. Exact library names (Pinecone, Celery, Prisma, dbt, ...) mostly appear only in code.
- Each persona has 2 off-niche gigs, and the main projects are described three ways (case study,
  repo, review).
- The CV PDF is rendered from `cv.md` with fpdf2 (core fonts, so non-Latin-1 characters are
  transliterated).

**Past proposals** (`scripts/label_proposals.py`, prompt version `proposal_v1`).
- 150 per persona, written for real K1 jobs. Styles are assigned before generation: 45% `specific`,
  25% `generic` (a stock opener as the first sentence), 15% `long` (380–560 words) and 15% `short`
  (30–75 words).
- **`specific` and `long` are LLM-written** (`gpt-oss-120b`, falling back to `gpt-oss-20b` at the
  daily cap), batched 4 or 3 jobs per call. The writer may cite only the persona's real projects.
- **`generic` and `short` are assembled from templates** (`generator.model: "template"`, prompt version
  `proposal_template_v1`, deterministic per job). Generic proposals are boilerplate by nature. Short
  ones cite the persona project whose words best overlap the job. This choice was forced by the Groq
  daily token caps (see section 3) and keeps those two styles reproducible.
- Missing screening answers are padded with `""`, which GigSim scores as unanswered.
- Bids are rule-based: hourly ≈ the persona rate × U(0.8, 1.05), sometimes capped near the job's top
  rate; fixed ≈ budget × U(0.8, 1.15).

**Outcomes** come from GigSim's stateless scorer.
- `POST /admin/score` on a dedicated GigSim instance (port 8091, DB `data/cache/gigsim_labels.sqlite`)
  seeded from `data/processed/gigsim_seed`.
- The scorer uses its **heuristic personalisation**. `GIGSIM_LLM_DISABLED=1` makes labels reproducible
  and keeps them off the shared Groq quota.
- Mapping: `hired`/`interview` → `won`, `replied` → `replied`, and everything else → `ignored`.
  `outcome_raw`, `p_reply`, `p_hire` and the score components are kept for analysis.

**Gold labels** come from `qwen/qwen3.8-27b` (182 jobs) and `claude-haiku-5-5` (568 jobs). The split is in `evals/datasets/LABELING.md`.
- `reasoning_effort: none` (Groq's way of turning off qwen's thinking), temperature 0.
- 5 jobs per call, compact JSON. Catalogue items are given short handles (E1..En) that are mapped
  back to evidence ids.
- See `evals/datasets/LABELING.md`.

## 7. Labelling rules (summary)

Full rules are in `evals/datasets/LABELING.md`. In short:
- `is_scam` / `has_injection` come from construction.
- `relevant_evidence_ids`, `requirements`/coverage, `required_skills` (K1) and `estimated_hours` come
  from qwen over the persona's full catalogue (CV, case studies, repos, reviews).
- `bid_or_skip` = coverage ≥ 0.6 AND not below the persona floor AND not a scam or injection.
- `fair_price_band` = K4 realised P25–P75 for the category (× LLM hours for fixed-price jobs).
- `required_skills` for K3 jobs are the client's own tags.
- `human_check.jsonl` holds 30 dev jobs with empty gold for a human to label.

## 8. Known limitations

- **Labels are single-pass LLM output.** Evidence relevance and coverage are not adjudicated, so use
  `human_check.jsonl` to measure agreement before trusting small differences.
- **Real K1 jobs are assumed legitimate.** Some K1 postings are probably real scams that we did not
  flag, so `is_scam` precision is solid but recall is only measured on constructed cases. K6 adds a
  real-world check, but its text is stop-word-stripped and lower-cased, and it covers employment ads,
  not freelance gigs.
- **The taxonomy is keyword rules.** Ambiguous titles ("AI video editor") go to the higher-priority
  category, and 18% of K1 lands in `other`. K2 and K4 are categorised by title only, and 44% of K4 is
  `other`, so per-category realised rates rest on fewer rows than the totals suggest.
- **Realised rates (K4) are much lower than the personas' rates** (`_all` P25–P75 = 10–35 USD/h).
  The fair band says what the market pays, not what a senior freelancer should charge.
- **The time window is narrow:** K1 covers 13–23 Feb 2024 almost entirely, so seasonality and drift
  are not represented. The dev and held-out windows are adjacent.
- **GigSim proposal-side fields are synthetic** (`proposals_count`, `screening_questions`,
  `experience_level` for K1, and all client data). Outcomes for past proposals come from the
  simulator's client model, not real hiring decisions, so they are only as good as that model.
- **Personas are synthetic.** They are internally consistent by construction, but the LLM adds
  plausible extra detail (for example, a review's "30% faster turnaround"). They are not verified
  facts about any real person.
- **K6 has no stated licence,** so it is used locally only and never committed.

## 9. Rebuild

```bash
# prerequisites: KAGGLE_API_TOKEN and GROQ_API_KEY in .env
make seed PY=.venv/Scripts/python          # Windows venv; plain `make seed` uses `python`
# or step by step:
.venv/Scripts/python scripts/download_kaggle.py     # K1-K6 -> data/raw/<key>/ (skips what exists)
.venv/Scripts/python scripts/build_personas.py      # data/personas/*
.venv/Scripts/python scripts/build_dataset.py       # processed data, taxonomy use, eval sets, GigSim seed, gold labels
.venv/Scripts/python scripts/label_proposals.py     # past proposals + GigSim outcomes (starts GigSim on :8091)
.venv/Scripts/python scripts/validate_data.py       # checks + count table
```

Every LLM call is cached in `data/cache/llm/`, so a rebuild with a warm cache costs no tokens and
reproduces the same outputs. `build_dataset.py --no-label` skips gold labelling (gold is then
rule-only).

Labeller selection:
- `GIGBID_LABEL_BACKEND=claude` (Haiku, needs `ANTHROPIC_API_KEY`), `qwen` (Groq, the default) or
  `cache` (no new calls).
- `GIGBID_LABEL_DEADLINE_MIN=N` stops issuing new label calls after N minutes; whatever is left gets
  `label_status: pending_llm_label`.
- `scripts/build_dataset.py --relabel-only` relabels the existing dev and held-out files without
  touching the GigSim seed, the splits or the personas.
- A full `build_dataset.py` run rewrites the seed. Its seeded RNGs and sorted inputs make the output
  the same on every run.
