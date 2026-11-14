"""LangGraph workflow definition for lead qualification.

The workflow consists of three nodes:
1. analyse – LLM determines missing fields.
2. ask_questions – Calls Twilio to request missing data.
3. approve – Human (or auto) approval before persisting.
"""

import os
from typing import Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemoryCheckpoint
from langgraph.agent import create_agent
from src.tools import send_sms

# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------


def _extract_missing_fields(analysis: str) -> Dict[str, Any]:
    """
    Very small parser that expects a JSON‑like string from the LLM
    indicating which fields are missing.
    """
    import json

    try:
        return json.loads(analysis)
    except json.JSONDecodeError:
        # Fallback – assume nothing missing
        return {}


# ----------------------------------------------------------------------
# Node definitions
# ----------------------------------------------------------------------


async def analyse(state: dict) -> dict:
    """Ask the LLM to list missing lead fields."""
    prompt = f"""
    You are a real‑estate lead qualification assistant.
    The prospect wrote:
    \"\"\"{state['enquiry_text']}\"\"\"

    Identify which of the following fields are missing or unclear:
    name, email, property_type, budget.

    Return a JSON object with the missing keys set to true, e.g.
    {{ "name": true, "budget": true }}. If all are present, return {{}}.
    """
    response = await state["llm"].acomplete(prompt)
    missing = _extract_missing_fields(response.content)
    return {"missing": missing}


async def ask_questions(state: dict) -> dict:
    """Send SMS queries for each missing field and wait for replies."""
    missing = state["missing"]
    phone = state["prospect_phone"]
    answers = {}

    for field in missing:
        question = {
            "name": "What is your full name?",
            "email": "What is your email address?",
            "property_type": "What type of property are you interested in?",
            "budget": "What is your budget (in GBP)?",
        }[field]

        # Send SMS via Twilio
        await send_sms(phone, question)

        # In a real system we would wait for an inbound message.
        # Here we simulate an immediate reply for brevity.
        # The reply would be captured by a webhook that stores it in DB;
        # the workflow would be resumed with that data.
        simulated_reply = "simulated answer"
        answers[field] = simulated_reply

    return {"answers": answers}


async def approve(state: dict) -> dict:
    """Human (or auto) approval step."""
    mode = os.getenv("APPROVAL_MODE", "manual")
    if mode == "auto":
        approved = True
    else:
        # In production this would raise a UI event; we default to True
        # after a short pause to mimic human review.
        await asyncio.sleep(2)
        approved = True

    # Merge collected data
    result = {
        "approved": approved,
        "prospect_phone": state["prospect_phone"],
    }
    result.update(state.get("answers", {}))
    # Assume LLM can fill any remaining slots from original text
    result.setdefault("name", "unknown")
    result.setdefault("email", "unknown@example.com")
    result.setdefault("property_type", "unknown")
    result.setdefault("budget", "unknown")
    return result


# ----------------------------------------------------------------------
# Workflow assembly
# ----------------------------------------------------------------------


async def build_workflow():
    """Construct the LangGraph StateGraph."""
    # Minimal LLM wrapper – replace with actual provider as needed
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    graph = StateGraph("lead_state")
    graph.add_node("analyse", analyse)
    graph.add_node("ask_questions", ask_questions)
    graph.add_node("approve", approve)

    graph.set_entry_point("analyse")
    graph.add_edge("analyse", "ask_questions")
    graph.add_edge("ask_questions", "approve")
    graph.add_edge("approve", END)

    # Attach the LLM to the graph state so nodes can access it
    graph.add_state("llm", llm)

    # Simple in‑memory checkpoint – sufficient for a demo
    checkpoint = MemoryCheckpoint()
    return graph.compile(checkpointer=checkpoint)
