"""Platform policy: versions from policy.yaml, the Connects formula and text checks."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

POLICY_PATH = Path(__file__).resolve().parent / "policy.yaml"


@dataclass(frozen=True)
class PolicyVersion:
    name: str
    rules: list[str]
    base: int
    per_100_usd: int
    max: int
    hourly_equiv_hours: int
    required_disclosure: str | None
    extra_threshold: int | None
    extra_connects: int

    def connects_formula(self) -> str:
        text = (
            f"value = budget (fixed) or hourly_high * {self.hourly_equiv_hours} (hourly); "
            f"cost = min({self.max}, {self.base} + floor(value / 100) * {self.per_100_usd})"
        )
        if self.extra_threshold is not None:
            text += f"; +{self.extra_connects} if proposals_count > {self.extra_threshold}"
        return text

    def public(self) -> dict[str, Any]:
        return {
            "version": self.name,
            "rules": list(self.rules),
            "connects_formula": self.connects_formula(),
            "required_disclosure": self.required_disclosure,
        }


class PolicyBook:
    def __init__(self, versions: dict[str, PolicyVersion], default: str):
        self.versions = versions
        self.default = default

    @classmethod
    def load(cls, path: Path = POLICY_PATH) -> PolicyBook:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        versions: dict[str, PolicyVersion] = {}
        for name, spec in (raw.get("versions") or {}).items():
            c = spec.get("connects") or {}
            extra = spec.get("extra_connects_if_proposals_over") or None
            versions[name] = PolicyVersion(
                name=name,
                rules=[str(r) for r in spec.get("rules") or []],
                base=int(c.get("base", 2)),
                per_100_usd=int(c.get("per_100_usd", 1)),
                max=int(c.get("max", 16)),
                hourly_equiv_hours=int(c.get("hourly_equiv_hours", 20)),
                required_disclosure=spec.get("required_disclosure"),
                extra_threshold=int(extra["threshold"]) if extra else None,
                extra_connects=int(extra["extra"]) if extra else 0,
            )
        default = raw.get("active") or next(iter(versions))
        if default not in versions:
            raise ValueError(f"policy.yaml: active version {default!r} is not defined")
        return cls(versions, default)

    def get(self, name: str) -> PolicyVersion:
        return self.versions[name]


def connects_cost(job: dict[str, Any], pv: PolicyVersion, proposals_count: int) -> int:
    if job.get("is_hourly"):
        value = (job.get("hourly_high") or 0) * pv.hourly_equiv_hours
    else:
        value = job.get("budget") or 0
    cost = min(pv.max, pv.base + math.floor(max(0.0, float(value)) / 100) * pv.per_100_usd)
    if pv.extra_threshold is not None and proposals_count > pv.extra_threshold:
        cost += pv.extra_connects
    return int(cost)


# --- text checks -------------------------------------------------------------------------------

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_PHONE_CANDIDATE = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")
_OFF_PLATFORM_TERMS = re.compile(
    r"\b(?:whats\s?app|telegram|skype|signal\s+app|wechat|viber|"
    r"pay\s?pal|venmo|zelle|cash\s?app|western\s+union|money\s?gram|payoneer\s+direct|"
    r"bitcoin|btc|usdt|tether|ethereum|crypto(?:currency)?\s+(?:payment|wallet|transfer)|"
    r"(?:pay|paid|payment)\s+(?:in|via|with)\s+crypto(?:currency)?|"
    r"wire\s+transfer|bank\s+transfer|direct\s+deposit|"
    r"off[\s-]platform|outside\s+(?:of\s+)?(?:the\s+)?(?:platform|upwork|gigsim))\b",
    re.IGNORECASE,
)
_GUARANTEE = re.compile(r"\bguarantee[sd]?\b|\bguaranteeing\b|100\s?%|\brisk[\s-]free\b", re.IGNORECASE)


def _violation(code: str, message: str, match: str) -> dict[str, str]:
    return {"code": code, "message": message, "match": match.strip()[:80]}


def find_off_platform(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for m in _EMAIL.finditer(text):
        found.append(_violation("off_platform_contact", "email addresses are not allowed", m.group()))
    for m in _PHONE_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 9 <= len(digits) <= 15:
            found.append(_violation("off_platform_contact", "phone numbers are not allowed", m.group()))
    for m in _OFF_PLATFORM_TERMS.finditer(text):
        found.append(
            _violation("off_platform_contact", "off-platform contact or payment is not allowed", m.group())
        )
    return found


def find_guarantees(text: str) -> list[dict[str, str]]:
    return [
        _violation("guarantee", "guarantees of results are not allowed", m.group())
        for m in _GUARANTEE.finditer(text)
    ]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def has_disclosure(pv: PolicyVersion, text: str) -> bool:
    if not pv.required_disclosure:
        return True
    return _norm(pv.required_disclosure) in _norm(text)


def check_proposal(pv: PolicyVersion, cover_letter: str, screening_answers: list[str]) -> list[dict[str, str]]:
    text = "\n".join([cover_letter, *screening_answers])
    violations = find_off_platform(text) + find_guarantees(text)
    if not has_disclosure(pv, cover_letter):
        violations.append(
            _violation(
                "missing_disclosure",
                f"policy {pv.name} requires the cover letter to include: {pv.required_disclosure}",
                "",
            )
        )
    return violations


def check_message(pv: PolicyVersion, text: str) -> list[dict[str, str]]:
    # The disclosure sentence is a proposal rule; chat messages only get the contact/guarantee checks.
    return find_off_platform(text) + find_guarantees(text)
