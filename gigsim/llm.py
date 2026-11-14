"""Cached chat completions against Groq's OpenAI-compatible API, with graceful fallback.

Every call returns `None` when there is no key, when `GIGSIM_LLM_DISABLED` is set, or when the
request fails, so callers always have a heuristic/template path. Successful results are cached in
the `llm_cache` table keyed by a hash of (model, kind, messages, params), which also makes repeat
calls deterministic. The API key is never logged.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

import httpx

from gigsim.db import Store

log = logging.getLogger("gigsim.llm")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class LLM:
    def __init__(
        self,
        store: Store,
        api_key: str | None,
        model: str,
        *,
        disabled: bool = False,
        timeout: float = 20.0,
    ):
        self._store = store
        self._api_key = api_key
        self.model = model
        self.disabled = disabled
        self.timeout = timeout

    def __repr__(self) -> str:  # never include the key
        return f"LLM(model={self.model!r}, enabled={self.enabled})"

    @property
    def enabled(self) -> bool:
        return bool(self._api_key) and not self.disabled

    def _cache_key(self, kind: str, messages: list[dict[str, str]], max_tokens: int) -> str:
        blob = json.dumps([self.model, kind, messages, max_tokens], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> str | None:
        with self._store.tx() as conn:
            row = conn.execute("SELECT value FROM llm_cache WHERE hash = ?", (key,)).fetchone()
        return row["value"] if row else None

    def _cache_put(self, key: str, value: str) -> None:
        with self._store.tx() as conn:
            conn.execute(
                "INSERT INTO llm_cache(hash, value) VALUES (?, ?) ON CONFLICT(hash) DO NOTHING",
                (key, value),
            )

    def chat(self, kind: str, system: str, user: str, *, max_tokens: int = 300) -> str | None:
        """Return the assistant text, or None if the LLM is unavailable. Must not be called inside
        an open `Store.tx()`."""
        if not self.enabled:
            return None
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        key = self._cache_key(kind, messages, max_tokens)
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        if self.model.startswith("openai/gpt-oss"):
            # Reasoning model: keep reasoning short so the answer fits in max_tokens.
            body["reasoning_effort"] = "low"
        try:
            resp = httpx.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            log.warning("llm %s: request failed (%s)", kind, type(exc).__name__)
            return None
        if resp.status_code != 200:
            log.warning("llm %s: HTTP %s", kind, resp.status_code)
            return None
        try:
            content = resp.json()["choices"][0]["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError):
            log.warning("llm %s: unexpected response shape", kind)
            return None
        content = strip_thinking(content).strip()
        if not content:
            return None
        self._cache_put(key, content)
        return content


def strip_thinking(text: str) -> str:
    """Remove `<think>...</think>` blocks some reasoning models put inline."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    if "<think>" in text.lower():  # unterminated block: nothing usable after it
        text = text[: text.lower().index("<think>")]
    return text


def parse_rating(text: str | None, low: int = 1, high: int = 5) -> int | None:
    """Pull a 1..5 rating out of free text defensively ("Rating: 4", "4/5", "**4**", "four")."""
    if not text:
        return None
    t = text.strip()
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    patterns = [
        r"(?:rating|score)\s*[:=]?\s*\**\s*([1-5])\b",
        r"\b([1-5])\s*(?:/|out of)\s*5\b",
        r"^\W*([1-5])\W*$",
        r"\b([1-5])\b",
    ]
    for pat in patterns:
        matches = re.findall(pat, t, flags=re.IGNORECASE | re.MULTILINE)
        if matches:
            value = int(matches[-1] if pat.endswith(r"\b([1-5])\b") else matches[0])
            if low <= value <= high:
                return value
    m = re.search(r"\b(one|two|three|four|five)\b", t, flags=re.IGNORECASE)
    if m:
        return words[m.group(1).lower()]
    return None
