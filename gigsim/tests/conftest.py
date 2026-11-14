from __future__ import annotations

import os

# Set before importing gigsim.app: the module-level app reads the environment at import time.
os.environ["GIGSIM_ERROR_RATE"] = "0"
os.environ["GIGSIM_LLM_DISABLED"] = "1"  # tests never touch the network

from collections.abc import Callable, Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from gigsim.app import create_app  # noqa: E402
from gigsim.config import Config  # noqa: E402

ADMIN = {"X-Admin-Token": "test-admin"}
AI = {"Authorization": "Bearer gigsim-token-ai"}
WEB = {"Authorization": "Bearer gigsim-token-web"}
DATA = {"Authorization": "Bearer gigsim-token-data"}

STRONG_LETTER = (
    "Double bookings are the classic failure in appointment apps, so for your 6-store bike-fitting launch "
    "I would enforce availability in PostgreSQL itself: an exclusion constraint on staff and time range plus "
    "a transaction per booking, so two customers can never take the same slot. Last year I built and shipped "
    "a booking system for a 9-location physio chain with React, TypeScript, Node.js (Fastify) and PostgreSQL; "
    "it handled 12,000 bookings a month with zero double bookings and cut no-shows by 31% with SMS reminders. "
    "For you I would deliver the customer flow (store, service, slot), staff availability rules, the 24-hour "
    "cancellation policy, email and SMS reminders and the admin schedule view, deployed on Fly.io with CI. "
    "Which SMS provider do your stores already use?"
)
STRONG_ANSWERS = [
    "I would add a PostgreSQL exclusion constraint on staff and time range so the database itself rejects "
    "overlapping bookings, run each booking in a serializable transaction, and return a clear conflict to the "
    "second customer together with the nearest free slots."
]
GENERIC_LETTER = (
    "Dear hiring manager, I am a highly skilled developer with many years of experience. "
    "I can do this job very well. Please hire me."
)


def make_config(tmp_path: Path, **overrides) -> Config:
    base = dict(
        db_path=tmp_path / "gigsim.sqlite",
        seed_dir=tmp_path / "no-seed-dir",  # missing -> built-in fixtures
        admin_token="test-admin",
        rate_per_min=100_000,
        error_rate=0.0,
        clock_speed=0,
        seed=42,
        llm_disabled=True,
        groq_api_key=None,
    )
    base.update(overrides)
    return Config(**base)


@pytest.fixture
def make_client(tmp_path: Path) -> Iterator[Callable[..., TestClient]]:
    opened: list[TestClient] = []

    def factory(**overrides) -> TestClient:
        cfg = make_config(tmp_path / f"run{len(opened)}", **overrides)
        cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
        c = TestClient(create_app(cfg))
        c.__enter__()
        opened.append(c)
        return c

    yield factory
    for c in opened:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


def create_draft(client: TestClient, headers: dict, key: str, **body):
    payload = {"screening_answers": [], **body}
    return client.post("/v1/proposals/drafts", json=payload, headers={**headers, "Idempotency-Key": key})


def submit(client: TestClient, headers: dict, draft_id: str, key: str, dry_run: bool = False):
    return client.post(
        f"/v1/proposals/drafts/{draft_id}/submit",
        params={"dry_run": str(dry_run).lower()},
        headers={**headers, "Idempotency-Key": key},
    )


def balance(client: TestClient, headers: dict) -> int:
    return client.get("/v1/connects", headers=headers).json()["balance"]


def advance(client: TestClient, minutes: int) -> dict:
    r = client.post("/admin/clock/advance", json={"minutes": minutes}, headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()


def all_events(client: TestClient, headers: dict) -> list[dict]:
    events, cursor = [], 0
    while True:
        r = client.get("/v1/events", params={"after": cursor, "limit": 50}, headers=headers).json()
        if not r["events"]:
            return events
        events += r["events"]
        cursor = r["next_cursor"]
