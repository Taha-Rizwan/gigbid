"""PII masking for logs and traces, and encryption for stored OAuth tokens."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
from typing import Any

from cryptography.fernet import Fernet

_PATTERNS = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[EMAIL]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CARD]"),
    (re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"), "[IBAN]"),
    (re.compile(r"(?<![\w-])\+?\d(?:[ ().-]?\d){8,}(?![\w-])"), "[PHONE]"),  # 9+ digits; not dates or versions
    (re.compile(r"(?i)\b(bearer|token|api[_-]?key|password|secret)\b(\s*[:=]\s*|\s+)\S+"), r"\1=[REDACTED]"),
]


def mask(text: str) -> str:
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


def mask_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return mask(obj)
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if k.lower() in {"token", "access_token", "refresh_token", "password", "authorization"} else mask_obj(v)) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [mask_obj(v) for v in obj]
    return obj


class PIIFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask(str(record.msg))
        if record.args:
            record.args = tuple(mask_obj(a) for a in (record.args if isinstance(record.args, tuple) else (record.args,)))
        return True


def install_log_masking() -> None:
    for h in logging.getLogger().handlers or [logging.StreamHandler()]:
        h.addFilter(PIIFilter())
    if not logging.getLogger().handlers:
        h = logging.StreamHandler()
        h.addFilter(PIIFilter())
        logging.getLogger().addHandler(h)
    logging.getLogger().setLevel(logging.INFO)


def _fernet() -> Fernet:
    key = os.environ.get("TOKEN_ENCRYPTION_KEY")
    if not key:  # derive a stable key from the app secret so dev works; production sets its own
        secret = os.environ.get("APP_SECRET_KEY", "dev-only-change-me").encode()
        key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest()).decode()
    return Fernet(key.encode())


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode())


def decrypt(token: bytes) -> str:
    return _fernet().decrypt(bytes(token)).decode()
