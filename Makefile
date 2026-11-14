.PHONY: install api test lint eval eval-smoke eval-gigsim seed validate-data
install:
	python -m pip install -e ".[dev]"

api:
	uvicorn apps.api.main:app --reload --port 8000

test:
	pytest -q

lint:
	ruff check .

# Evaluation harness (evals/runners/). Every number lands in evals/results/*.json.
# Needs the eval GigSim on :8091 (make eval-gigsim in another shell). LLM calls are cached in
# data/cache/evals/, so a rerun only pays for what is missing. EVAL_PROFILE=open runs on Groq.
EVAL_PROFILE ?= paid
EVAL_ARGS ?= --profile $(EVAL_PROFILE)
eval-gigsim:
	GIGSIM_SEED_DIR=data/processed/gigsim_seed GIGSIM_DB=data/cache/gigsim_eval.sqlite GIGSIM_ERROR_RATE=0 	GIGSIM_RATE_PER_MIN=0 GIGSIM_LLM_DISABLED=1 $(PY) -m uvicorn gigsim.app:app --port 8091

eval:
	$(PY) -m evals.runners.rag_eval $(EVAL_ARGS) --llm-limit 20
	$(PY) -m evals.runners.ablation $(EVAL_ARGS)
	$(PY) -m evals.runners.decision_eval $(EVAL_ARGS) --limit 30 --k6-limit 100
	$(PY) -m evals.runners.proposal_eval $(EVAL_ARGS) --limit 10 --variants v0_naive,best
	$(PY) -m evals.runners.injection_eval $(EVAL_ARGS)
	$(PY) -m evals.runners.multiagent_compare $(EVAL_ARGS) --limit 7
	$(PY) -m evals.runners.tool_granularity $(EVAL_ARGS)
	$(PY) -m evals.runners.model_profiles --profiles paid,open,open_alt --limit 5 --proposal-limit 10
	$(PY) -m evals.runners.judge_calibration
	$(PY) scripts/make_results_table.py

# 30 jobs (10 per persona), used by CI; fails when evals/thresholds.yaml is crossed.
eval-smoke:
	$(PY) -m evals.runners.rag_eval $(EVAL_ARGS) --limit 10 --variants v0_naive,v2_hybrid,v3_rerank --tag _smoke
	$(PY) -m evals.runners.decision_eval $(EVAL_ARGS) --limit 10 --k6-limit 0 --tag _smoke
	$(PY) -m evals.runners.proposal_eval $(EVAL_ARGS) --limit 2 --variants v3_rerank --no-judge --tag _smoke
	$(PY) -m evals.runners.smoke
	$(PY) -m evals.runners.check_thresholds

# Data layer: Kaggle K1-K6 -> personas -> processed data, GigSim seed, eval sets -> past proposals.
# Every LLM call is cached in data/cache/llm/, so a rerun costs no tokens.
PY ?= python
seed:
	$(PY) scripts/download_kaggle.py
	$(PY) scripts/build_personas.py
	$(PY) scripts/build_dataset.py
	$(PY) scripts/label_proposals.py
	$(PY) scripts/validate_data.py

validate-data:
	$(PY) scripts/validate_data.py
