# rag-eval-kit

**Purpose**  
A minimal reference implementation of a Retrieval‑Augmented Generation (RAG) pipeline for a contract‑question‑answering assistant. The system:

* Retrieves candidate clauses from a Pinecone vector index and a BM25 inverted index.  
* Re‑ranks the combined shortlist with a cross‑encoder model.  
* Returns the highest‑scoring clause together with a citation to the source document.  
* Provides an evaluation harness that compares the assistant’s answers to a lawyer‑written answer key (120 questions) and reports accuracy and unsupported‑citation rates.

**How it works**  

1. **Embedding** – User queries are embedded with OpenAI embeddings (via the `openai` package).  
2. **First‑stage retrieval** –  
   * **BM25** over pre‑tokenised contract texts (stored in SQLite).  
   * **Vector search** in Pinecone.  
   The two result sets are merged and deduplicated.  
3. **Second‑stage re‑ranking** – A cross‑encoder (e.g. `sentence‑transformers/all‑MiniLM‑L6‑v2`) scores each (query, clause) pair; the top‑k are sorted by this score.  
4. **Answer selection** – The highest‑scoring clause is returned as the answer, together with its document ID and clause number.  
5. **Evaluation** – `pytest` reads the answer key (`answers.json`) and runs the pipeline on every question, computing exact‑match accuracy and the proportion of answers without a citation.

**Setup**

```bash
# Clone the repo
git clone https://example.com/rag-eval-kit.git
cd rag-eval-kit

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Environment variables (create a .env file or export manually)
export OPENAI_API_KEY=your-openai-key
export PINECONE_API_KEY=your-pinecone-key
export PINECONE_INDEX=contract-clauses
```

**Running the service**

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

POST a JSON payload to `http://localhost:8000/answer`:

```json
{
  "question": "What is the notice period for termination?"
}
```

**Running the evaluation**

```bash
pytest -q tests/test_evaluation.py
```

The test prints a short report, e.g.:

```
Accuracy: 86.0%
Unsupported citations: 0.3%
```

**Notes**

* Only two external libraries are mentioned in the README to keep it concise, but the code imports the full set required for the pipeline.  
* All secrets are read from environment variables; no hard‑coded credentials are shipped.
