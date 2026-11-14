# lead-agent

## Purpose
An autonomous lead‑qualification agent for a real‑estate CRM.  
It parses inbound enquiry texts, asks the prospect for any missing details via SMS, and, after a brief human review, stores a qualified lead in the CRM database.

## How it works
- **Ingestion** – New enquiry rows are streamed from PostgreSQL.  
- **LLM reasoning** – A LangGraph workflow analyses the enquiry, determines missing fields, and generates follow‑up questions.  
- **Tool calling** – The workflow calls Twilio to send SMS prompts to the prospect.  
- **Human approval** – A simple web UI (or Slack notification) lets a sales rep approve the generated lead before it is persisted.  
- **Persistence** – Approved leads are written back to PostgreSQL, ready for the sales team.

## Setup
1. Install dependencies  
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Set required environment variables  

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Access key for the LLM provider |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_FROM_NUMBER` | Phone number used to send SMS |
| `DATABASE_URL` | PostgreSQL connection string (e.g. `postgresql://user:pass@host/db`) |

3. Initialise the database schema (see `src/db.py` for the SQL).

## Usage
Run the agent as a background service:

```bash
python -m src.main
```

The agent will poll for new enquiries, process them, and log actions to the console.  
Human approval can be simulated by setting the `APPROVAL_MODE` environment variable to `auto` (for testing) or `manual` (default).
