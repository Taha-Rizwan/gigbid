"""Idempotency, dry_run and policy v1/v2 for drafts and submission."""

from __future__ import annotations

from gigsim.tests.conftest import (
    ADMIN,
    AI,
    DATA,
    STRONG_ANSWERS,
    STRONG_LETTER,
    WEB,
    all_events,
    balance,
    create_draft,
    submit,
)

BOOKING = dict(job_id="job_013", cover_letter=STRONG_LETTER, screening_answers=STRONG_ANSWERS,
               bid_amount=3400, rate_type="fixed")


def test_idempotent_draft_and_submit_never_spend_twice(client):
    start = balance(client, WEB)

    d1 = create_draft(client, WEB, "draft-key-1", **BOOKING)
    d2 = create_draft(client, WEB, "draft-key-1", **BOOKING)
    assert d1.status_code == d2.status_code == 200
    assert "Idempotent-Replay" not in d1.headers
    assert d2.headers["Idempotent-Replay"] == "true"
    assert d1.json() == d2.json()
    draft = d1.json()
    assert draft["status"] == "draft" and draft["job_id"] == "job_013"

    s1 = submit(client, WEB, draft["draft_id"], "submit-key-1")
    s2 = submit(client, WEB, draft["draft_id"], "submit-key-1")
    assert s1.status_code == s2.status_code == 200, s1.text
    assert s2.headers["Idempotent-Replay"] == "true"
    assert s1.json() == s2.json()
    assert s1.json()["status"] == "submitted"
    assert s1.json()["connects_spent"] == draft["connects_cost"]
    assert balance(client, WEB) == start - draft["connects_cost"] == s1.json()["balance"]

    # A different key for the same draft is rejected and spends nothing.
    s3 = submit(client, WEB, draft["draft_id"], "submit-key-2")
    assert s3.status_code == 409 and s3.json()["error"] == "already_submitted"
    # A second draft for the same job cannot be submitted either.
    d3 = create_draft(client, WEB, "draft-key-2", **BOOKING).json()
    s4 = submit(client, WEB, d3["draft_id"], "submit-key-3")
    assert s4.status_code == 409 and s4.json()["error"] == "already_applied"
    assert balance(client, WEB) == start - draft["connects_cost"]
    assert len(client.get("/v1/proposals", headers=WEB).json()["proposals"]) == 1

    # Reusing a key on a different endpoint is a conflict, not a silent replay.
    s5 = submit(client, WEB, d3["draft_id"], "draft-key-1")
    assert s5.status_code == 409 and s5.json()["error"] == "idempotency_key_reused"


def test_idempotency_key_is_required_and_scoped_per_account(client):
    r = client.post("/v1/proposals/drafts", json=BOOKING, headers=WEB)
    assert r.status_code == 400
    assert r.json() == {"error": "missing_idempotency_key", "detail": r.json()["detail"]}

    draft = create_draft(client, WEB, "same-key", **BOOKING).json()
    r = client.post(f"/v1/proposals/drafts/{draft['draft_id']}/submit", headers=WEB)
    assert r.status_code == 400 and r.json()["error"] == "missing_idempotency_key"

    other = create_draft(client, AI, "same-key", **BOOKING)
    assert other.status_code == 200 and "Idempotent-Replay" not in other.headers
    assert other.json()["draft_id"] != draft["draft_id"]
    # Another account cannot submit someone else's draft.
    assert submit(client, AI, draft["draft_id"], "k").status_code == 404


def test_dry_run_changes_nothing(client):
    draft = create_draft(client, WEB, "dr-1", **BOOKING).json()
    before = {
        "balance": balance(client, WEB),
        "proposals": client.get("/v1/proposals", headers=WEB).json(),
        "threads": client.get("/v1/threads", headers=WEB).json(),
        "events": all_events(client, WEB),
        "job": client.get("/v1/jobs/job_013", headers=WEB).json(),
    }

    r = submit(client, WEB, draft["draft_id"], "sub-1", dry_run=True)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "Idempotent-Replay" not in r.headers
    assert body["would_send"]["cover_letter"] == STRONG_LETTER
    assert body["would_send"]["bid_amount"] == 3400
    assert body["connects_cost"] == draft["connects_cost"]
    assert body["balance_after"] == before["balance"] - draft["connects_cost"]
    assert body["policy_check"] == {"ok": True, "violations": []}

    # Repeat the dry run, then check nothing moved.
    assert submit(client, WEB, draft["draft_id"], "sub-1", dry_run=True).json() == body
    after = {
        "balance": balance(client, WEB),
        "proposals": client.get("/v1/proposals", headers=WEB).json(),
        "threads": client.get("/v1/threads", headers=WEB).json(),
        "events": all_events(client, WEB),
        "job": client.get("/v1/jobs/job_013", headers=WEB).json(),
    }
    assert after == before

    # The same key still works for the real submit afterwards (dry runs are not recorded).
    real = submit(client, WEB, draft["draft_id"], "sub-1")
    assert real.status_code == 200 and "Idempotent-Replay" not in real.headers
    assert real.json()["status"] == "submitted"


def _codes(resp) -> set[str]:
    return {v["code"] for v in resp.json().get("violations", [])}


def test_policy_v1_vs_v2(client):
    pol = client.get("/v1/policy", headers=DATA).json()
    assert pol["version"] == "v1" and pol["required_disclosure"] is None
    assert len(pol["rules"]) == 4 and "connects_formula" in pol

    # job_019: fixed $1200, 21 proposals (> 20). job_020: fixed $800, 8 proposals.
    assert client.get("/v1/jobs/job_019", headers=DATA).json()["connects_cost"] == 2 + 12
    assert client.get("/v1/jobs/job_020", headers=DATA).json()["connects_cost"] == 2 + 8

    letter = (
        "Your regional sales data in SQL Server maps cleanly onto a star schema with orders as the fact table. "
        "I built a Power BI dashboard for a 40-rep distributor last year with DAX measures for YoY, MTD and "
        "rolling 12 months, plus row-level security per region, and delivered it in 3 weeks."
    )
    v1_draft = create_draft(client, DATA, "p-1", job_id="job_019", cover_letter=letter, bid_amount=1100,
                            rate_type="fixed").json()
    assert v1_draft["connects_cost"] == 14
    assert submit(client, DATA, v1_draft["draft_id"], "dry-1", dry_run=True).json()["policy_check"]["ok"] is True

    r = client.post("/admin/policy", json={"version": "v2"}, headers=ADMIN)
    assert r.status_code == 200
    pol2 = client.get("/v1/policy", headers=DATA).json()
    disclosure = "This proposal was drafted with AI assistance and reviewed by me."
    assert pol2["version"] == "v2" and pol2["required_disclosure"] == disclosure
    assert len(pol2["rules"]) == 5

    # v2 adds 4 Connects when proposals_count > 20, nothing otherwise.
    assert client.get("/v1/jobs/job_019", headers=DATA).json()["connects_cost"] == 14 + 4
    assert client.get("/v1/jobs/job_020", headers=DATA).json()["connects_cost"] == 10

    start = balance(client, DATA)
    dry = submit(client, DATA, v1_draft["draft_id"], "dry-2", dry_run=True).json()
    assert dry["policy_check"]["ok"] is False and dry["connects_cost"] == 18
    rejected = submit(client, DATA, v1_draft["draft_id"], "sub-1")
    assert rejected.status_code == 422
    assert rejected.json()["error"] == "policy_violation" and "missing_disclosure" in _codes(rejected)
    assert balance(client, DATA) == start

    ok_draft = create_draft(client, DATA, "p-2", job_id="job_019", cover_letter=letter + " " + disclosure,
                            bid_amount=1100, rate_type="fixed").json()
    ok = submit(client, DATA, ok_draft["draft_id"], "sub-2")
    assert ok.status_code == 200, ok.text
    assert ok.json()["connects_spent"] == 18
    assert balance(client, DATA) == start - 18

    # Back to v1: no disclosure needed, but contact details and guarantees are still rejected.
    client.post("/admin/policy", json={"version": "v1"}, headers=ADMIN)
    for key, bad, code in [
        ("e", letter + " Email me at mei.chen@example.com to move faster.", "off_platform_contact"),
        ("w", letter + " Ping me on WhatsApp +44 7700 900123.", "off_platform_contact"),
        ("g", letter + " I guarantee a 100% accurate dashboard.", "guarantee"),
    ]:
        d = create_draft(client, DATA, f"bad-{key}", job_id="job_020", cover_letter=bad, bid_amount=700,
                         rate_type="fixed").json()
        r = submit(client, DATA, d["draft_id"], f"bad-sub-{key}")
        assert r.status_code == 422 and code in _codes(r), r.text
    assert balance(client, DATA) == start - 18

    assert client.post("/admin/policy", json={"version": "v9"}, headers=ADMIN).status_code == 422


def test_rate_type_must_match_job_and_validation_errors_use_error_shape(client):
    r = create_draft(client, WEB, "rt", job_id="job_013", cover_letter="x" * 50, bid_amount=50, rate_type="hourly")
    assert r.status_code == 422 and r.json()["error"] == "rate_type_mismatch"
    r = create_draft(client, WEB, "neg", job_id="job_013", cover_letter="hello", bid_amount=-5, rate_type="fixed")
    assert r.status_code == 422 and r.json()["error"] == "validation_error" and "detail" in r.json()
    r = create_draft(client, WEB, "unreleased", job_id="job_017", cover_letter="hi", bid_amount=500, rate_type="fixed")
    assert r.status_code == 404 and r.json()["error"] == "job_not_found"


def test_insufficient_connects(client):
    # Drain acct_ai with 16-Connect jobs (60 -> 44 -> 28 -> 12), then a 16-Connect submit fails.
    letter = ("I built and shipped production retrieval systems with Python and PyTorch, measured with "
              "precision at 5 and faithfulness on a 200-question set, over 3 years of client work. " * 2)
    jobs = [("job_001", 3000, "fixed"), ("job_003", 4500, "fixed"), ("job_006", 3800, "fixed"),
            ("job_029", 4000, "fixed")]
    results = []
    for i, (job_id, bid, rt) in enumerate(jobs):
        d = create_draft(client, AI, f"ic-{i}", job_id=job_id, cover_letter=letter, bid_amount=bid, rate_type=rt)
        results.append(submit(client, AI, d.json()["draft_id"], f"ic-sub-{i}"))
    assert [r.status_code for r in results] == [200, 200, 200, 402]
    body = results[-1].json()
    assert body["error"] == "insufficient_connects" and body["balance"] == 12 and body["connects_cost"] == 16
