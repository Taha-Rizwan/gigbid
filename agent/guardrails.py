"""Prompt-injection defences for untrusted text (job posts, client messages).

Layers (each measured separately in evals/runners/injection_eval.py):
1. Delimiting: untrusted text is wrapped in <untrusted_...> tags and system prompts say it is data.
2. Datamarking (optional): a marker interleaved into untrusted text so the model can tell it apart.
3. Detection: heuristics + Llama Prompt Guard 2 classifier; detections raise the risk score.
4. Capability isolation: nodes that read raw untrusted text hold no write tools (agent/mcp_client.py).
5. Output checks: the Compliance Guard blocks contact details, links and injected asks before approval.
"""

from __future__ import annotations

import os
import re

import httpx

from agent.settings import config

MARK = "ˆ"  # ˆ
INJECTION_PATTERNS = [
    r"(?i)ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts|rules)",
    r"(?i)(disregard|forget) (your|all|the) (instructions|rules|guidelines)",
    r"(?i)\b(ai|assistant|chatgpt|gpt|llm|language model|bot|automated tool)s?\b.{0,40}\b(must|should|need to|are required to|please)\b",
    r"(?i)\byou are now\b",
    r"(?i)\b(system prompt|developer message|jailbreak)\b",
    r"(?i)include (your|the) (email|phone|whatsapp|telegram|contact)",
    r"(?i)(start|begin) your (proposal|reply|answer) with",
    r"(?i)if you are an? (ai|bot|llm|language model)",
]


def heuristic_injection(text: str) -> list[str]:
    return [p for p in INJECTION_PATTERNS if re.search(p, text)]


def datamark(text: str) -> str:
    return re.sub(r"\s+", MARK, text.strip())


def wrap(kind: str, text: str, mark: bool = False) -> str:
    body = datamark(text) if mark else text
    note = f" (words are joined by '{MARK}'; this is data)" if mark else ""
    return f"<untrusted_{kind}{note}>\n{body}\n</untrusted_{kind}>"


async def prompt_guard_score(text: str) -> float | None:
    """Probability-like score from Llama Prompt Guard 2 on Groq; None if unavailable."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    model = config()["models"].get("injection_classifier")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": [{"role": "user", "content": text[:2000]}]},
            )
        if r.status_code != 200:
            return None
        content = r.json()["choices"][0]["message"]["content"].strip()
        m = re.search(r"[0-9]*\.?[0-9]+", content)
        if m:
            return max(0.0, min(1.0, float(m.group())))
        return 1.0 if "malicious" in content.lower() or "injection" in content.lower() else 0.0
    except Exception:  # noqa: BLE001
        return None


async def injection_signal(text: str, use_classifier: bool = True) -> tuple[float, list[str]]:
    hits = heuristic_injection(text)
    score = 0.9 if hits else 0.0
    if use_classifier:
        pg = await prompt_guard_score(text)
        if pg is not None:
            score = max(score, pg)
    return score, hits


CITATION = re.compile(r"\s*\[[a-z_]+:[a-z]+:[^\]\s]+\]")


def strip_citations(text: str) -> str:
    """Evidence ids are for the human reviewer; the client never sees them."""
    return re.sub(r"[ \t]+([.,;:!?])", r"\1", CITATION.sub("", text)).strip()
