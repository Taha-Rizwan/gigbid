"""MCP servers exercised through an in-memory MCP client (no network, no LLM)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "personas"


@pytest.fixture(autouse=True)
def _fixture_personas(monkeypatch):
    if not FIXTURES.exists():
        from tests.fixtures.build_fixture_persona import main

        main()
    monkeypatch.setenv("GIGBID_PERSONAS_DIR", str(FIXTURES))
    import rag.ingest.loaders as loaders
    import rag.retriever as retriever

    monkeypatch.setattr(loaders, "PERSONAS_DIR", FIXTURES)
    monkeypatch.setattr(retriever, "pipeline", lambda name=None: __import__(
        "rag.variants.v2_hybrid", fromlist=["PIPELINE"]).PIPELINE)
    retriever._indexes.clear()


def _payload(result):
    if result.structuredContent:
        return result.structuredContent
    return json.loads(result.content[0].text)


async def test_portfolio_search_returns_cited_evidence():
    from mcp_servers.portfolio.server import mcp

    async with connect(mcp._mcp_server) as c:
        res = await c.call_tool("search_evidence", {"requirement": "nightly retraining of a recommendation model",
                                                    "k": 3, "persona_id": "ai_ml"})
        out = _payload(res)
        ids = [i["evidence_id"] for i in out["items"]]
        assert out["persona_id"] == "ai_ml" and len(ids) == 3
        assert all(i.startswith("ai_ml:") for i in ids)
        assert "ai_ml:repo:ops-kit" in ids  # skill only visible in the code, not the README


async def test_portfolio_case_study_and_resources():
    from mcp_servers.portfolio.server import mcp

    async with connect(mcp._mcp_server) as c:
        doc = _payload(await c.call_tool("get_case_study", {"evidence_id": "ai_ml:case:legal-rag-assistant"}))
        assert "pgvector" in doc["text"]
        res = await c.read_resource("portfolio://case/ai_ml:case:legal-rag-assistant")
        assert "Contract search assistant" in res.contents[0].text
        prompts = [p.name for p in (await c.list_prompts()).prompts]
        assert "answer_screening_question" in prompts


async def test_portfolio_rejects_unknown_persona():
    from mcp_servers.portfolio.server import mcp

    async with connect(mcp._mcp_server) as c:
        res = await c.call_tool("search_evidence", {"requirement": "anything", "persona_id": "nobody"})
        assert res.isError


async def test_marketplace_write_requires_valid_schema():
    from mcp_servers.marketplace.server import mcp

    async with connect(mcp._mcp_server) as c:
        bad = await c.call_tool("create_proposal_draft", {
            "draft": {"job_id": "job_001", "cover_letter": "too short", "bid_amount": -5, "rate_type": "weekly"},
            "idempotency_key": "k"})
        assert bad.isError  # min lengths, positive bid and rate_type enum are enforced by the schema


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="needs Postgres for the idempotency table")
async def test_marketplace_dry_run_against_gigsim(monkeypatch, tmp_path):
    """dry_run returns what would be sent and its cost without writing anything."""
    import httpx

    from gigsim.app import create_app
    from mcp_servers.marketplace import server as srv
    from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter

    monkeypatch.setenv("GIGSIM_DB", str(tmp_path / "g.sqlite"))
    monkeypatch.setenv("GIGSIM_ERROR_RATE", "0")
    monkeypatch.setenv("GIGSIM_LLM_DISABLED", "1")
    monkeypatch.setenv("GIGSIM_SEED_DIR", "gigsim/fixtures")
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://gigsim")

    async def adapter_for(_user):
        return GigSimAdapter("http://gigsim", "gigsim-token-ai", client)

    monkeypatch.setattr(srv, "adapter_for", adapter_for)
    async with connect(srv.mcp._mcp_server) as c:
        out = _payload(await c.call_tool("create_proposal_draft", {
            "draft": {"job_id": "job_004", "cover_letter": "x" * 60, "bid_amount": 2000, "rate_type": "fixed"},
            "idempotency_key": "test-dry-run-0001", "dry_run": True}))
        assert out["dry_run"] is True and out["result"]["connects_cost"] > 0
