"""Disk-cached Groq chat client used by the data build scripts.

* Every call is cached in data/cache/llm/<sha256>.json keyed on the full request, so reruns are
  free and resumable.
* 429s are handled by reading `retry-after` and backing off. A daily-limit 429 (RPD/TPD) raises
  DailyLimitError so the caller can fall back to another model.
* The API key is read from the environment / .env and is never printed or logged.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import threading
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "cache" / "llm"
URL = "https://api.groq.com/openai/v1/chat/completions"

load_dotenv(ROOT / ".env")

_lock = threading.Lock()
SESSION_USAGE: dict[str, dict[str, int]] = {}  # model -> {calls, cached, prompt, completion, total}
_model_sems: dict[str, threading.Semaphore] = {}
_exhausted: set[str] = set()
_client: httpx.Client | None = None


class DailyLimitError(RuntimeError):
    pass


class LLMError(RuntimeError):
    pass


def _http() -> httpx.Client:
    global _client
    if _client is None:
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise LLMError("GROQ_API_KEY missing (set it in .env)")
        _client = httpx.Client(timeout=httpx.Timeout(30, read=240),
                               headers={"Authorization": f"Bearer {key}"})
    return _client


def _sem(model: str, n: int = 3) -> threading.Semaphore:
    with _lock:
        if model not in _model_sems:
            _model_sems[model] = threading.Semaphore(n)
        return _model_sems[model]


def _record(model: str, usage: dict | None, cached: bool) -> None:
    with _lock:
        u = SESSION_USAGE.setdefault(model, {"calls": 0, "cached": 0, "prompt": 0, "completion": 0, "total": 0})
        u["calls"] += 1
        if cached:
            u["cached"] += 1
            return
        usage = usage or {}
        u["prompt"] += int(usage.get("prompt_tokens", 0))
        u["completion"] += int(usage.get("completion_tokens", 0))
        u["total"] += int(usage.get("total_tokens", 0))
    _log_spend(model, usage or {})


def _log_spend(model: str, usage: dict) -> None:
    """Append fresh (non-cached) spend, including retries whose output was discarded."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with _lock, open(CACHE_DIR.parent / "llm_spend.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"model": model, "prompt": usage.get("prompt_tokens", 0),
                                "completion": usage.get("completion_tokens", 0),
                                "total": usage.get("total_tokens", 0)}) + "\n")
    except OSError:
        pass


def _parse_seconds(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        pass
    total, ok = 0.0, False
    for num, unit in re.findall(r"([\d.]+)(ms|h|m|s)", v):
        ok = True
        total += float(num) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
    return total if ok else None


def cache_key(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def build_payload(model: str, messages: list[dict], *, json_mode: bool = False, temperature: float = 0.4,
                  max_tokens: int | None = None, seed: int = 0, reasoning_effort: str | None = None) -> dict:
    if reasoning_effort is None and model.startswith("openai/gpt-oss"):
        reasoning_effort = "low"
    if reasoning_effort is None and model.startswith("qwen/"):
        reasoning_effort = "none"
    payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature, "seed": seed}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    return payload


def is_cached(model: str, messages: list[dict], **kw) -> bool:
    return (CACHE_DIR / f"{cache_key(build_payload(model, messages, **kw))}.json").exists()


def chat(model: str, messages: list[dict], *, json_mode: bool = False, temperature: float = 0.4,
         max_tokens: int | None = None, seed: int = 0, reasoning_effort: str | None = None,
         max_attempts: int = 8, validate=None) -> dict:
    """Return {content, usage, model, cached}. Raises DailyLimitError / LLMError.

    `validate(content) -> bool` lets callers reject an output (it is retried, never cached).
    """
    payload = build_payload(model, messages, json_mode=json_mode, temperature=temperature,
                            max_tokens=max_tokens, seed=seed, reasoning_effort=reasoning_effort)
    key = cache_key(payload)
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        _record(model, data.get("usage"), cached=True)
        return {"content": data["content"], "usage": data.get("usage"), "model": model, "cached": True}
    if model in _exhausted:
        raise DailyLimitError(f"{model}: daily limit reached earlier in this run")

    attempt = 0
    bad_outputs = 0
    with _sem(model):
        while True:
            attempt += 1
            try:
                r = _http().post(URL, json=payload)
            except httpx.HTTPError as e:
                if attempt >= max_attempts * 3:
                    raise LLMError(f"{model}: transport error {type(e).__name__}") from None
                time.sleep(min(60, 2 ** min(attempt, 6)) + random.random())
                continue
            if r.status_code == 200:
                j = r.json()
                content = j["choices"][0]["message"].get("content") or ""
                usage = j.get("usage", {})
                ok = True
                if json_mode:
                    try:
                        parse_json(content)
                    except ValueError:
                        ok = False
                if ok and validate is not None:
                    try:
                        ok = bool(validate(content))
                    except Exception:  # noqa: BLE001
                        ok = False
                if not ok:
                    _record(model, usage, cached=False)
                    bad_outputs += 1
                    if bad_outputs >= max_attempts:
                        raise LLMError(f"{model}: output failed validation {bad_outputs} times")
                    payload["seed"] = payload.get("seed", 0) + 1000  # nudge; cache key stays the original
                    continue
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
                tmp.write_text(json.dumps({"request": payload, "content": content, "usage": usage,
                                           "created": time.strftime("%Y-%m-%dT%H:%M:%S")},
                                          ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, path)
                _record(model, usage, cached=False)
                return {"content": content, "usage": usage, "model": model, "cached": False}
            try:
                err = r.json().get("error", {})
            except Exception:  # noqa: BLE001
                err = {"message": r.text[:300]}
            msg = str(err.get("message", ""))
            if r.status_code == 429:
                if re.search(r"per day|\(RPD\)|\(TPD\)", msg):
                    _exhausted.add(model)
                    raise DailyLimitError(f"{model}: daily limit reached ({msg[:160]})")
                if "Request too large" in msg:
                    raise LLMError(f"{model}: request too large: {msg[:200]}")
                wait = _parse_seconds(r.headers.get("retry-after")) or 5.0
                m = re.search(r"try again in ([\dhms.]+)", msg)
                if m:
                    wait = max(wait, _parse_seconds(m.group(1)) or 0)
                if attempt >= 200:
                    raise LLMError(f"{model}: still rate limited")
                time.sleep(min(wait, 120) + random.uniform(0.2, 1.5))
                continue
            if r.status_code == 400 and "json_validate_failed" in json.dumps(err):
                bad_outputs += 1
                if bad_outputs >= max_attempts:
                    raise LLMError(f"{model}: json_validate_failed")
                payload["seed"] = payload.get("seed", 0) + 1000
                continue
            if r.status_code >= 500 and attempt < max_attempts * 2:
                time.sleep(min(60, 2 ** min(attempt, 6)) + random.random())
                continue
            raise LLMError(f"{model}: HTTP {r.status_code}: {msg[:300]}")


def chat_fallback(models: list[str], messages: list[dict], **kw) -> dict:
    """Try models in order; move on only when one hits its daily limit.

    Cache hits on any model in the chain are preferred, so a rerun reproduces the same output.
    """
    for m in models:
        kw2 = {k: v for k, v in kw.items() if k not in ("validate", "max_attempts")}
        if is_cached(m, messages, **kw2):
            return chat(m, messages, **kw)
    last: Exception | None = None
    for m in models:
        try:
            return chat(m, messages, **kw)
        except DailyLimitError as e:
            last = e
            continue
    raise last or LLMError("no models")


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.M)


def parse_json(text: str) -> Any:
    t = text.strip()
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    t2 = _FENCE.sub("", t).strip()
    try:
        return json.loads(t2)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", t, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError("not JSON")


def chat_json(models: str | list[str], messages: list[dict], **kw) -> tuple[Any, dict]:
    models = [models] if isinstance(models, str) else models
    res = chat_fallback(models, messages, json_mode=True, **kw)
    return parse_json(res["content"]), res


def cache_totals() -> dict[str, dict[str, int]]:
    """Sum the usage stored in every cache file: the tokens it cost to build the cache."""
    out: dict[str, dict[str, int]] = {}
    if not CACHE_DIR.exists():
        return out
    for p in CACHE_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        m = d.get("request", {}).get("model", "?")
        u = d.get("usage") or {}
        o = out.setdefault(m, {"calls": 0, "prompt": 0, "completion": 0, "total": 0})
        o["calls"] += 1
        o["prompt"] += int(u.get("prompt_tokens", 0))
        o["completion"] += int(u.get("completion_tokens", 0))
        o["total"] += int(u.get("total_tokens", 0))
    return out


def spend_totals() -> dict[str, dict[str, int]]:
    """Every fresh call ever made (including retried/discarded outputs), from llm_spend.jsonl."""
    out: dict[str, dict[str, int]] = {}
    p = CACHE_DIR.parent / "llm_spend.jsonl"
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        o = out.setdefault(d["model"], {"calls": 0, "prompt": 0, "completion": 0, "total": 0})
        o["calls"] += 1
        for k in ("prompt", "completion", "total"):
            o[k] += int(d.get(k, 0))
    return out


def print_session_usage() -> None:
    for m, u in sorted(SESSION_USAGE.items()):
        print(f"  {m:24s} calls={u['calls']:5d} cached={u['cached']:5d} tokens={u['total']:8d}")
