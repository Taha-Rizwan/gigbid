# GigBid Portfolio MCP server

A read-only [MCP](https://modelcontextprotocol.io) server that lets any MCP host (Claude Desktop, Cursor, …) search a
freelancer's portfolio for evidence: case studies, code repositories, client reviews, CV and past proposals with their
outcomes. Built with the official MCP Python SDK.

## Tools, resources, prompts

| Kind | Name | What it does |
|---|---|---|
| tool | `search_evidence(requirement, k, filters, persona_id)` | Evidence items that prove a requirement (type, source, date, outcome) |
| tool | `get_case_study(evidence_id)` | Full text and metadata of one item |
| tool | `list_skills(persona_id)` | Skills in the portfolio with item counts |
| resource | `portfolio://case/{evidence_id}`, `portfolio://proposal/{evidence_id}`, `portfolio://profile/{persona_id}` | Load full items |
| prompt | `answer_screening_question`, `fit_for_job`, `cover_letter_outline` | Ready-made freelancer workflows |

All tools are annotated `readOnlyHint: true`.

## Install and run

No clone needed (requires [uv](https://docs.astral.sh/uv/)):

```bash
uvx --from git+https://github.com/Taha-Rizwan/gigbid gigbid-portfolio-mcp --stdio
```

From a clone of the repo:

```bash
uv sync
uv run python -m mcp_servers.portfolio.server --stdio      # stdio, for desktop hosts
uv run python -m mcp_servers.portfolio.server              # Streamable HTTP on :8102/mcp (bearer auth)
```

## Use it in Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gigbid-portfolio": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Taha-Rizwan/gigbid", "gigbid-portfolio-mcp", "--stdio"],
      "env": { "PORTFOLIO_PERSONA": "ai_ml" }
    }
  }
}
```

Then ask, for example: *"Which of my projects prove I can build a RAG chatbot over PDFs? Cite evidence ids."*

## Use your own portfolio

Point `GIGBID_PERSONAS_DIR` at a folder laid out like `data/personas/<persona_id>/`:

```
my-portfolio/
  me/
    profile.json            # name, title, skills, hourly_rate
    cv.md                   # or cv.pdf
    case_studies/*.md       # YAML front matter: evidence_id, title, project, skills, date, outcome
    repos/<repo>/README.md and source files
    reviews.jsonl           # {evidence_id, client_name, project, rating, text, date}
    proposals.jsonl         # optional: past proposals with outcome won / replied / ignored
```

and set `PORTFOLIO_PERSONA=me`. The bundled personas (`ai_ml`, `fullstack`, `data_analyst`) are synthetic.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `PORTFOLIO_PERSONA` | `ai_ml` | Default portfolio to search |
| `GIGBID_PERSONAS_DIR` | `data/personas` | Folder holding portfolios |
| `RAG_VARIANT` | from `agent/config.yaml` | Retrieval pipeline (`v2_hybrid` is fastest; `v8_corrective` is the evaluated best and needs an LLM key) |
| `MCP_AUTH_TOKEN` | `dev-mcp-token` | Bearer token for the HTTP transport |

Embeddings run locally on CPU (fastembed / ONNX); no API key is needed for `v0`–`v5` retrieval.
