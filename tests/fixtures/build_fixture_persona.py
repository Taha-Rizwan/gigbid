"""Builds a tiny synthetic persona under tests/fixtures/personas/ai_ml so unit and integration tests
(and CI) never depend on the generated corpus in data/personas."""

import json
from pathlib import Path

OUT = Path(__file__).parent / "personas" / "ai_ml"

CASES = {
    "legal-rag-assistant": ("Contract search assistant for a law firm", ["RAG", "LangChain", "pgvector", "FastAPI"],
        "legal", "2025-03",
        "A 40-lawyer firm needed answers from 6,000 scanned contracts. I built an OCR + chunking pipeline, embedded "
        "clauses into pgvector and served a FastAPI chat endpoint with citations to the source page. Answer accuracy on "
        "a 120-question test set went from 61% with keyword search to 89%. Lawyers now get cited answers in seconds."),
    "churn-uplift-telco": ("Churn prediction for a telecom subscription business", ["Python", "scikit-learn", "XGBoost", "SHAP"],
        "telecom", "2024-08",
        "Built a churn model on 2M customer-months with gradient boosting, calibrated probabilities and SHAP explanations "
        "for the retention team. Precision at the top decile was 0.62; targeted offers cut monthly churn by 1.4 points."),
    "pcb-defect-vision": ("Visual inspection model for circuit boards", ["PyTorch", "YOLO", "OpenCV", "ONNX"],
        "manufacturing", "2023-11",
        "Trained a YOLO detector on 9,000 labelled PCB images, exported to ONNX for the line's edge box. Recall on solder "
        "defects reached 96% at 30 fps, replacing two manual inspection steps."),
    "ticket-classifier-llm": ("Support ticket routing with a fine-tuned small language model", ["Transformers", "LoRA", "Python"],
        "saas", "2025-06",
        "Fine-tuned a 1B-parameter model with LoRA on 40k historical tickets to route them to 14 queues. Macro-F1 0.87 vs "
        "0.71 for the old rules; deployed behind a queue worker with nightly retraining."),
}

REPO_README = "# ops-kit\n\nScripts I use on client projects.\n"
REPO_CODE = '''from airflow import DAG
from airflow.operators.python import PythonOperator

def retrain_and_deploy():
    """Nightly retrain of the recommendation model, push to SageMaker endpoint, roll back on drift."""
    ...

with DAG("recsys_retrain", schedule="@daily", catchup=False) as dag:
    PythonOperator(task_id="retrain", python_callable=retrain_and_deploy)
'''


def main() -> None:
    (OUT / "case_studies").mkdir(parents=True, exist_ok=True)
    (OUT / "repos" / "ops-kit" / "src").mkdir(parents=True, exist_ok=True)
    (OUT / "profile.json").write_text(json.dumps({
        "persona_id": "ai_ml", "name": "Test Persona", "title": "ML engineer", "hourly_rate": 60,
        "skills": ["Python", "RAG", "PyTorch", "MLOps"], "years_experience": 6, "industries": ["legal", "telecom"],
        "bio": "Fixture persona for tests.", "gigsim_account_id": "acct_ai", "synthetic": True,
        "generator": {"model": "hand-written", "prompt_version": "fixture", "seed": 0}}, indent=1))
    (OUT / "cv.md").write_text("# Test Persona\nML engineer, 6 years. Python, PyTorch, RAG systems, MLOps on AWS.\n")
    for slug, (title, skills, industry, date, body) in CASES.items():
        (OUT / "case_studies" / f"{slug}.md").write_text(
            f"---\nevidence_id: ai_ml:case:{slug}\ntitle: {title}\nproject: {slug}\nclient_industry: {industry}\n"
            f"date: '{date}'\nskills: {json.dumps(skills)}\noutcome: delivered\nsynthetic: true\n---\n{body}\n")
    (OUT / "repos" / "ops-kit" / "README.md").write_text(REPO_README)
    (OUT / "repos" / "ops-kit" / "src" / "dag.py").write_text(REPO_CODE)
    (OUT / "reviews.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"evidence_id": "ai_ml:review:001", "client_name": "Legal client", "project": "legal-rag-assistant", "rating": 5,
         "text": "Delivered a contract Q&A tool our lawyers actually use. Clear communication.", "date": "2025-04"},
        {"evidence_id": "ai_ml:review:002", "client_name": "Telco client", "project": "churn-uplift-telco", "rating": 5,
         "text": "The churn model paid for itself in the first month.", "date": "2024-09"},
    ]) + "\n")
    (OUT / "proposals.jsonl").write_text("\n".join(json.dumps(p) for p in [
        {"evidence_id": "ai_ml:proposal:001", "job_ref": "fixture", "job_title": "RAG over PDFs",
         "job_excerpt": "Need RAG over PDFs", "cover_letter": "Your team loses hours searching contracts. I built a cited "
         "contract search assistant for a law firm that took accuracy from 61% to 89%.", "screening_answers": [],
         "bid_amount": 3000, "rate_type": "fixed", "date": "2025-05", "outcome": "won", "style": "specific", "synthetic": True},
        {"evidence_id": "ai_ml:proposal:002", "job_ref": "fixture", "job_title": "ML model",
         "job_excerpt": "Need ML model", "cover_letter": "Dear hiring manager, I am a highly skilled ML expert.",
         "screening_answers": [], "bid_amount": 900, "rate_type": "fixed", "date": "2025-01", "outcome": "ignored",
         "style": "generic", "synthetic": True},
    ]) + "\n")


if __name__ == "__main__":
    main()
    print("fixture persona written to", OUT)
