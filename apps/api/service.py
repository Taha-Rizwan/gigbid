"""Service layer behind the routers. Every query is scoped by user_id (tenant)."""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Request, Response, UploadFile
from fastapi.responses import RedirectResponse
from sse_starlette.sse import EventSourceResponse

from agent.handoffs import ApprovalRequest, ClaimLabel
from agent.marketplace_port import MarketplaceUnavailable as _PortUnavailable
from agent.settings import config
from apps.api import jobs_queue
from apps.api.runs import _serialisable, engine, mirror, new_run
from apps.api.schemas import (
    AnalyticsOut,
    ApprovalIn,
    ApprovalResult,
    CategoryRate,
    ConversationOut,
    ConversationSummary,
    HealthOut,
    InboxItem,
    InboxOut,
    JobDetail,
    LoginIn,
    MemoryItem,
    MemoryOut,
    MessageOut,
    ParagraphOut,
    PipelineCard,
    PipelineOut,
    PortfolioItemOut,
    ProfileIn,
    ProfileOut,
    RegenerateIn,
    RegisterIn,
    RunEvent,
    RunOut,
    RunStarted,
    SavedSearch,
    ServiceStatus,
    StudioOut,
    UploadResult,
    UserOut,
)
from apps.api.settings import settings
from common import db

ph = PasswordHasher()
COOKIE = "gigbid_session"
PERSONA_TOKEN = {"ai_ml": "gigsim-token-ai", "fullstack": "gigsim-token-web", "data_analyst": "gigsim-token-data",
                 "own": "gigsim-token-ai"}


class MarketplaceUnavailable(Exception):
    def __init__(self, detail: str, queued: int = 0):
        super().__init__(detail)
        self.queued = queued


def new_trace_id() -> str:
    return uuid.uuid4().hex


# ------------------------------------------------------------------ lifecycle

async def startup() -> None:
    from common.security import install_log_masking

    install_log_masking()
    await db.migrate()
    await engine.open()
    await seed_reviewer()


async def shutdown() -> None:
    await engine.close()
    await db.close()


async def seed_reviewer() -> None:
    """Reviewer login preloaded with a persona (password from REVIEWER_PASSWORD, never committed)."""
    pw = settings.reviewer_password or os.environ.get("REVIEWER_PASSWORD")
    if not pw:
        return
    row = await db.fetchrow("select user_id from users where email=%s", settings.reviewer_email)
    if row:
        return
    uid = "u_reviewer"
    await db.execute("insert into users (user_id, email, name, password_hash) values (%s,%s,%s,%s) on conflict do nothing",
                     uid, settings.reviewer_email, "Reviewer", ph.hash(pw))
    await db.execute("insert into profiles (user_id, data, gigsim_token) values (%s,%s,%s) on conflict do nothing",
                     uid, json.dumps(ProfileIn(persona="ai_ml").model_dump() | {"onboarded": True}), PERSONA_TOKEN["ai_ml"])
    for q in ("machine learning", "rag llm", "data pipeline"):
        await db.execute("insert into searches (search_id, user_id, data) values (%s,%s,%s)",
                         uuid.uuid4().hex[:10], uid, json.dumps(SavedSearch(query=q).model_dump()))


# ------------------------------------------------------------------ auth

def _token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": datetime.now(UTC) + timedelta(days=7)}, settings.app_secret_key, "HS256")


def _set_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(COOKIE, _token(user_id), httponly=True, samesite="lax",
                        secure=settings.app_env == "production", max_age=7 * 86400, path="/")


async def _user(user_id: str) -> UserOut | None:
    row = await db.fetchrow(
        "select u.user_id, u.email, u.name, coalesce((p.data->>'onboarded')::boolean, false) as onboarded "
        "from users u left join profiles p on p.user_id=u.user_id where u.user_id=%s", user_id)
    return UserOut(**row) if row else None


async def user_from_session(token: str) -> UserOut | None:
    try:
        return await _user(jwt.decode(token, settings.app_secret_key, ["HS256"])["sub"])
    except jwt.PyJWTError:
        return None


async def register(body: RegisterIn, response: Response) -> UserOut:
    if await db.fetchrow("select 1 from users where email=%s", body.email.lower()):
        raise HTTPException(409, "email already registered")
    uid = "u_" + uuid.uuid4().hex[:12]
    await db.execute("insert into users (user_id, email, name, password_hash) values (%s,%s,%s,%s)",
                     uid, body.email.lower(), body.name, ph.hash(body.password))
    await db.execute("insert into profiles (user_id, data, gigsim_token) values (%s,%s,%s)",
                     uid, json.dumps(ProfileIn().model_dump() | {"onboarded": False}), PERSONA_TOKEN["ai_ml"])
    _set_cookie(response, uid)
    return await _user(uid)


async def login(body: LoginIn, response: Response) -> UserOut:
    row = await db.fetchrow("select user_id, password_hash from users where email=%s", body.email.lower())
    try:
        if not row or not ph.verify(row["password_hash"], body.password):
            raise VerifyMismatchError
    except VerifyMismatchError:
        raise HTTPException(401, "wrong email or password") from None
    _set_cookie(response, row["user_id"])
    return await _user(row["user_id"])


def logout(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


# ------------------------------------------------------------------ profile

async def _profile(user_id: str) -> dict:
    row = await db.fetchrow("select data from profiles where user_id=%s", user_id)
    return (row or {}).get("data") or ProfileIn().model_dump()


async def get_profile(user: UserOut) -> ProfileOut:
    p = await _profile(user.user_id)
    spent = await db.fetchrow(
        "select coalesce(sum(connects_spent),0) as s from proposals where user_id=%s and updated_at > now() - interval '7 days'",
        user.user_id)
    up = await db.fetchrow("select 1 from oauth_tokens where user_id=%s and provider='upwork'", user.user_id)
    return ProfileOut(**{k: v for k, v in p.items() if k in ProfileIn.model_fields}, user_id=user.user_id,
                      connects_spent_this_week=int(spent["s"]), upwork_connected=bool(up))


async def put_profile(user: UserOut, body: ProfileIn) -> ProfileOut:
    if body.marketplace_mode == "upwork_live" and not await db.fetchrow(
            "select 1 from oauth_tokens where user_id=%s and provider='upwork'", user.user_id):
        raise HTTPException(409, "connect your Upwork account first")
    data = body.model_dump() | {"onboarded": True}
    await db.execute(
        """insert into profiles (user_id, data, gigsim_token) values (%s,%s,%s) on conflict (user_id)
           do update set data=excluded.data, gigsim_token=excluded.gigsim_token, updated_at=now()""",
        user.user_id, json.dumps(data), PERSONA_TOKEN.get(body.persona, PERSONA_TOKEN["ai_ml"]))
    return await get_profile(user)


async def list_searches(user: UserOut) -> list[SavedSearch]:
    rows = await db.fetch("select search_id, data from searches where user_id=%s order by search_id", user.user_id)
    return [SavedSearch(**r["data"], search_id=r["search_id"]) if "search_id" not in r["data"]
            else SavedSearch(**(r["data"] | {"search_id": r["search_id"]})) for r in rows]


async def create_search(user: UserOut, body: SavedSearch) -> SavedSearch:
    sid = uuid.uuid4().hex[:10]
    await db.execute("insert into searches (search_id, user_id, data) values (%s,%s,%s)",
                     sid, user.user_id, json.dumps(body.model_dump(exclude={"search_id"})))
    return body.model_copy(update={"search_id": sid})


async def delete_search(user: UserOut, search_id: str) -> None:
    await db.execute("delete from searches where user_id=%s and search_id=%s", user.user_id, search_id)


# ------------------------------------------------------------------ portfolio

async def list_portfolio(user: UserOut) -> list[PortfolioItemOut]:
    from rag.ingest.loaders import load_persona

    persona = (await _profile(user.user_id)).get("persona", "ai_ml")
    docs = await asyncio.to_thread(load_persona, persona) if persona != "own" else []
    rows = await db.fetch("select data, created_at from workspace_items where user_id=%s and kind='upload' order by created_at",
                          user.user_id)
    out = [PortfolioItemOut(evidence_id=d.evidence_id, type=d.type, title=d.title, project=d.project, skills=d.skills,
                            outcome=d.outcome, synthetic=d.synthetic) for d in docs]
    out += [PortfolioItemOut(**{k: v for k, v in r["data"].items() if k in PortfolioItemOut.model_fields},
                             added_at=r["created_at"]) for r in rows]
    return out


async def upload_portfolio(user: UserOut, files: list[UploadFile]) -> UploadResult:
    """Stores the upload; the Portfolio MCP server re-indexes it incrementally on next search."""
    from rag.ingest.chunking import structured_chunks
    from rag.ingest.loaders import load_upload

    persona = (await _profile(user.user_id)).get("persona", "ai_ml")
    items, chunks = [], 0
    for i, f in enumerate(files):
        data = await f.read()
        if len(data) > 5_000_000:
            raise HTTPException(413, f"{f.filename} is larger than 5 MB")
        doc = load_upload(persona, f.filename or f"upload-{i}", data, i)
        chunks += len(structured_chunks(doc))
        item = PortfolioItemOut(evidence_id=doc.evidence_id, type="upload", title=doc.title, project=doc.project,
                                skills=doc.skills, synthetic=False)
        await db.execute("insert into workspace_items (id, user_id, kind, data) values (%s,%s,'upload',%s)",
                         uuid.uuid4().hex[:12], user.user_id,
                         json.dumps(item.model_dump(mode="json") | {"persona_id": persona, "text": doc.text}))
        items.append(item)
    return UploadResult(added=len(items), chunks=chunks, items=items)


# ------------------------------------------------------------------ jobs

async def inbox(user: UserOut, status, recommendation, q, sort, limit, offset) -> InboxOut:
    where, args = ["user_id=%s"], [user.user_id]
    if status:
        where.append("status=%s")
        args.append(status)
    if recommendation:
        where.append("recommendation=%s")
        args.append(recommendation)
    if q:
        where.append("(job->>'title' ilike %s or job->>'snippet' ilike %s)")
        args += [f"%{q}%", f"%{q}%"]
    order = {"fit": "fit_score desc nulls last, posted_at desc nulls last", "newest": "posted_at desc nulls last",
             "price": "price desc nulls last"}[sort]
    rows = await db.fetch(f"select * from jobs where {' and '.join(where)} order by {order} limit %s offset %s",
                          *args, limit, offset)
    total = await db.fetchrow(f"select count(*) as n from jobs where {' and '.join(where)}", *args)
    items = []
    for r in rows:
        j, a = r["job"], r["analysis"] or {}
        risk = a.get("risk_report") or {}
        price = a.get("price_quote") or {}
        items.append(InboxItem(
            job_id=r["job_id"], title=j.get("title", ""), snippet=j.get("snippet") or (j.get("description") or "")[:280],
            category=j.get("category"), posted_at=r["posted_at"], status=r["status"], fit_score=r["fit_score"],
            risk_score=r["risk_score"], risk_level=risk.get("level"), risk_flags=risk.get("flags", []),
            recommendation=r["recommendation"], price=r["price"], rate_type=price.get("rate_type"),
            connects_cost=r["connects_cost"], thread_id=r["thread_id"]))
    return InboxOut(items=items, total=total["n"], marketplace_status=(await health()).status)


async def scout_now(user: UserOut) -> RunStarted:
    run_id = await new_run(user.user_id, f"scout-{user.user_id}", "bid", None, new_trace_id())
    await jobs_queue.enqueue("scout_user", user.user_id, run_id)
    return RunStarted(run_id=run_id, thread_id=f"scout-{user.user_id}", status="queued")


async def _job_row(user_id: str, job_id: str) -> dict:
    row = await db.fetchrow("select * from jobs where user_id=%s and job_id=%s", user_id, job_id)
    if not row:
        raise HTTPException(404, "job not in your inbox")
    return row


async def job_detail(user: UserOut, job_id: str) -> JobDetail:
    r = await _job_row(user.user_id, job_id)
    j, a = r["job"], r["analysis"] or {}
    dec = a.get("decision") or {}
    trace = await db.fetchrow("select trace_url from runs where user_id=%s and job_id=%s order by started_at desc limit 1",
                              user.user_id, job_id)
    return JobDetail(
        job_id=job_id, title=j.get("title", ""), description=j.get("description") or j.get("snippet", ""),
        category=j.get("category"), budget=j.get("budget"), hourly_low=j.get("hourly_low"), hourly_high=j.get("hourly_high"),
        is_hourly=j.get("is_hourly"), country=j.get("country"), posted_at=r["posted_at"], connects_cost=r["connects_cost"],
        client=j.get("client"), status=r["status"], thread_id=r["thread_id"], job_spec=a.get("job_spec"),
        risk_report=a.get("risk_report"), fit_report=a.get("fit_report"), price_quote=a.get("price_quote"),
        decision=dec.get("decision"), decision_reasons=dec.get("reasons", []), trace_url=(trace or {}).get("trace_url"))


async def analyze(user: UserOut, job_id: str) -> RunStarted:
    """Starts (or re-starts) the bid graph thread for this job. Drafting follows automatically on 'bid'."""
    await _job_row(user.user_id, job_id)
    thread_id = f"bid-{user.user_id}-{job_id}"
    snap = await engine.bid.aget_state({"configurable": {"thread_id": thread_id}})
    if snap.next and "approval" in snap.next:
        raise HTTPException(409, "a draft is already waiting for your approval in the studio")
    if snap.values:  # re-analysis starts a fresh thread version
        thread_id = f"{thread_id}-r{uuid.uuid4().hex[:4]}"
    run_id = await new_run(user.user_id, thread_id, "bid", job_id, new_trace_id())
    await db.execute("update jobs set status='analysing', thread_id=%s where user_id=%s and job_id=%s",
                     thread_id, user.user_id, job_id)
    profile = await _profile(user.user_id)
    await jobs_queue.enqueue("run_start", run_id, user.user_id, thread_id,
                             {"persona_id": profile.get("persona", "ai_ml"), "job_id": job_id, "profile": profile},
                             profile.get("model_profile"))
    return RunStarted(run_id=run_id, thread_id=thread_id, status="queued")


async def skip(user: UserOut, job_id: str, reason: str) -> None:
    await _job_row(user.user_id, job_id)
    await db.execute("update jobs set status='skipped', recommendation='skip' where user_id=%s and job_id=%s",
                     user.user_id, job_id)
    await db.execute("insert into feedback (user_id, thread_id, action, reason) values (%s,%s,'skip',%s)",
                     user.user_id, job_id, reason)


# ------------------------------------------------------------------ studio / approvals

def _paragraphs(text: str, claims) -> list[ParagraphOut]:
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    out = []
    for i, p in enumerate(paras):
        mine = [c for c in claims if _overlap(c.text, p) >= 0.6]
        out.append(ParagraphOut(index=i, text=p, claims=mine))
    return out


def _overlap(a: str, b: str) -> float:
    wa = set(re.findall(r"\w+", a.lower()))
    return len(wa & set(re.findall(r"\w+", b.lower()))) / max(1, len(wa))


async def _snapshot(user_id: str, thread_id: str):
    if not thread_id.startswith((f"bid-{user_id}-", f"conv-{user_id}|")):
        raise HTTPException(404, "not your thread")
    graph = engine.graph_for(thread_id)
    snap = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    if not snap.values:
        raise HTTPException(404, "thread not found")
    return graph, snap


def _pending(snap) -> dict | None:
    for t in snap.tasks or []:
        for i in t.interrupts or []:
            return i.value
    return None


async def studio(user: UserOut, thread_id: str) -> StudioOut:
    _, snap = await _snapshot(user.user_id, thread_id)
    s = snap.values
    draft = s.get("draft")
    if draft is None:
        raise HTTPException(409, "no draft yet: the job was skipped or is still being analysed")
    ver = s.get("verification") or {}
    pending = _pending(snap)
    active = await db.fetchrow("select run_id from runs where thread_id=%s and status in ('queued','running') "
                               "order by started_at desc limit 1", thread_id)
    trace = await db.fetchrow("select trace_url from runs where thread_id=%s order by started_at desc limit 1", thread_id)
    return StudioOut(
        thread_id=thread_id, job_id=s["job_id"], job_title=s["job"].title, status=s.get("status", "drafting"),
        version=draft.version, paragraphs=_paragraphs(draft.cover_letter, draft.claims),
        screening_questions=(s["job_spec"].screening_questions if s.get("job_spec") else []) or s["job"].screening_questions,
        screening_answers=draft.screening_answers, evidence=s.get("evidence") or [], critiques=s.get("critiques") or [],
        compliance=s.get("compliance"), price=s.get("price_quote"), risk=s.get("risk_report"), dry_run=s.get("dry_run"),
        unsupported_before=ver.get("first_before", 0),
        unsupported_after=sum(c.label == ClaimLabel.unsupported for c in draft.claims),
        pending_approval=ApprovalRequest(**pending) if pending else None,
        trace_url=(trace or {}).get("trace_url"), run_id=(active or {}).get("run_id"))


async def decide(user: UserOut, thread_id: str, body: ApprovalIn) -> ApprovalResult:
    _, snap = await _snapshot(user.user_id, thread_id)
    if not _pending(snap):
        raise HTTPException(409, "nothing is waiting for approval on this thread")
    if body.action == "reject" and not (body.reason or "").strip():
        raise HTTPException(422, "a reason is required to reject")
    if body.action == "edit" and not (body.edited_text or "").strip():
        raise HTTPException(422, "edited_text is required for an edit")
    await db.execute("insert into feedback (user_id, thread_id, action, reason, diff) values (%s,%s,%s,%s,%s)",
                     user.user_id, thread_id, body.action, body.reason,
                     json.dumps({"edited": bool(body.edited_text)}))
    job_id = snap.values.get("job_id")
    run_id = await new_run(user.user_id, thread_id, "conversation" if thread_id.startswith("conv-") else "bid",
                           job_id, new_trace_id())
    profile = await _profile(user.user_id)
    await jobs_queue.enqueue("run_resume", run_id, user.user_id, thread_id, body.model_dump(), profile.get("model_profile"))
    status = {"approve": "submitted" if not thread_id.startswith("conv-") else "sent", "edit": "rechecking",
              "reject": "rejected" if not thread_id.startswith("conv-") else "message_rejected"}[body.action]
    return ApprovalResult(thread_id=thread_id, status=status, run_id=run_id,
                          detail="queued: progress is visible in the run viewer")


async def regenerate_paragraph(user: UserOut, thread_id: str, body: RegenerateIn) -> RunStarted:
    from agent import llm
    from agent.nodes.common import evidence_block

    _, snap = await _snapshot(user.user_id, thread_id)
    draft = snap.values["draft"]
    paras = [p for p in re.split(r"\n\s*\n", draft.cover_letter.strip()) if p.strip()]
    if body.paragraph_index >= len(paras):
        raise HTTPException(422, "no such paragraph")
    new_p = await llm.text("writer", llm.prompt_messages(
        "regenerate_paragraph",
        f"EVIDENCE:\n{evidence_block(snap.values.get('evidence') or [], 400)}\n\nFULL PROPOSAL:\n{draft.cover_letter}\n\n"
        f"PARAGRAPH {body.paragraph_index + 1} TO REWRITE:\n{paras[body.paragraph_index]}\n\n"
        f"INSTRUCTION: {body.instruction or 'make it more specific to the client'}"))
    paras[body.paragraph_index] = new_p.strip()
    new_draft = draft.model_copy(update={"cover_letter": "\n\n".join(paras), "version": draft.version + 1})
    run_id = await new_run(user.user_id, thread_id, "bid", snap.values.get("job_id"), new_trace_id())
    # re-enter the graph after the writer: verification, critic, compliance and a fresh approval
    await jobs_queue.enqueue("run_update", run_id, user.user_id, thread_id,
                             {"values": {"draft": new_draft.model_dump(mode="json")}, "as_node": "proposal_writer"})
    return RunStarted(run_id=run_id, thread_id=thread_id, status="queued")


async def pipeline(user: UserOut) -> PipelineOut:
    rows = await db.fetch("""select p.*, j.job->>'title' as title from proposals p
                             left join jobs j on j.user_id=p.user_id and j.job_id=p.job_id where p.user_id=%s
                             order by p.updated_at desc""", user.user_id)
    cols: dict[str, list[PipelineCard]] = {s: [] for s in ("drafted", "submitted", "viewed", "replied", "interview", "hired", "lost")}
    for r in rows:
        stage = r["stage"] if r["stage"] in cols else "lost"
        cols[stage].append(PipelineCard(job_id=r["job_id"], title=r["title"] or r["job_id"], stage=stage,
                                        bid_amount=r["bid_amount"], connects_spent=r["connects_spent"],
                                        updated_at=r["updated_at"], proposal_id=r["proposal_id"],
                                        conversation_thread_id=r["conversation_id"]))
    return PipelineOut(columns=cols)


# ------------------------------------------------------------------ messages

async def conversations(user: UserOut) -> list[ConversationSummary]:
    rows = await db.fetch("""select c.*, j.job->>'title' as title from conversations c
                             left join jobs j on j.user_id=c.user_id and j.job_id=c.job_id
                             where c.user_id=%s order by c.updated_at desc""", user.user_id)
    out = []
    for r in rows:
        st = r["state"] or {}
        out.append(ConversationSummary(
            conversation_id=r["conversation_id"], job_id=r["job_id"], job_title=r["title"],
            client_name=st.get("client_name"), last_message_at=r["updated_at"], unread=bool(st.get("unread")),
            pending_reply=st.get("status") == "awaiting_approval", intent=st.get("intent"), flags=st.get("flags") or []))
    return out


async def conversation(user: UserOut, conversation_id: str) -> ConversationOut:
    row = await db.fetchrow("select * from conversations where user_id=%s and conversation_id=%s", user.user_id, conversation_id)
    if not row:
        raise HTTPException(404, "conversation not found")
    box = await _box(user.user_id)
    try:
        msgs = await box.for_agent("liaison").call("list_messages", thread_id=conversation_id)
    except _PortUnavailable as exc:
        raise MarketplaceUnavailable(exc.detail) from exc
    gtid = row["graph_thread_id"]
    reply, pending, comp = None, None, None
    if gtid:
        snap = await engine.conv.aget_state({"configurable": {"thread_id": gtid}})
        if snap.values:
            reply = snap.values.get("reply")
            comp = snap.values.get("compliance")
            pending = _pending(snap)
    st = row["state"] or {}
    return ConversationOut(
        conversation_id=conversation_id, job_title=st.get("job_title"), client_name=st.get("client_name"),
        messages=[MessageOut(**{k: m.get(k) for k in MessageOut.model_fields}) for m in (msgs or [])],
        suggested_reply=reply.text if reply else None, proposed_slots=reply.proposed_slots if reply else [],
        intent=st.get("intent"), flags=st.get("flags") or [], graph_thread_id=gtid, awaiting_approval=bool(pending),
        pending_approval=ApprovalRequest(**pending) if pending else None, compliance=comp)


async def draft_reply(user: UserOut, conversation_id: str) -> RunStarted:
    row = await db.fetchrow("select * from conversations where user_id=%s and conversation_id=%s", user.user_id, conversation_id)
    if not row:
        raise HTTPException(404, "conversation not found")
    thread_id = f"conv-{user.user_id}|{conversation_id}|{uuid.uuid4().hex[:6]}"
    await db.execute("update conversations set graph_thread_id=%s where user_id=%s and conversation_id=%s",
                     thread_id, user.user_id, conversation_id)
    run_id = await new_run(user.user_id, thread_id, "conversation", row["job_id"], new_trace_id())
    profile = await _profile(user.user_id)
    await jobs_queue.enqueue("run_start", run_id, user.user_id, thread_id,
                             {"user_id": user.user_id, "persona_id": profile.get("persona", "ai_ml"),
                              "conversation_id": conversation_id, "job_id": row["job_id"], "profile": profile},
                             profile.get("model_profile"))
    return RunStarted(run_id=run_id, thread_id=thread_id, status="queued")


# ------------------------------------------------------------------ runs

async def list_runs(user: UserOut, limit: int) -> list[RunOut]:
    rows = await db.fetch("select * from runs where user_id=%s order by started_at desc limit %s", user.user_id, limit)
    return [_run_out(r, []) for r in rows]


def _run_out(r: dict, events: list[dict]) -> RunOut:
    conv = r["thread_id"].split("|")[1] if r["thread_id"].startswith("conv-") else None
    return RunOut(run_id=r["run_id"], thread_id=r["thread_id"], graph=r["graph"], job_id=r["job_id"], status=r["status"],
                  started_at=r["started_at"], finished_at=r["finished_at"], tokens=r["tokens"] or 0,
                  cost_usd=r["cost_usd"] or 0.0, latency_s=r["latency_s"], trace_url=r["trace_url"],
                  conversation_id=conv, events=[RunEvent(**e) for e in events])


async def get_run(user: UserOut, run_id: str) -> RunOut:
    r = await db.fetchrow("select * from runs where user_id=%s and run_id=%s", user.user_id, run_id)
    if not r:
        raise HTTPException(404, "run not found")
    ev = await db.fetch("select seq, at, node, kind, summary, data from run_events where run_id=%s order by seq", run_id)
    return _run_out(r, ev)


async def stream_run(user: UserOut, run_id: str, request: Request):
    """SSE of run events; resumes from Last-Event-ID so a refresh never loses progress."""
    await get_run(user, run_id)
    last = int(request.headers.get("last-event-id") or 0)

    async def gen():
        nonlocal last
        idle = 0
        while not await request.is_disconnected():
            rows = await db.fetch("select seq, at, node, kind, summary, data from run_events where run_id=%s and seq>%s "
                                  "order by seq", run_id, last)
            for e in rows:
                last = e["seq"]
                yield {"id": str(e["seq"]), "event": "message",
                       "data": RunEvent(**e).model_dump_json()}
            status = (await db.fetchrow("select status from runs where run_id=%s", run_id))["status"]
            if status in ("done", "interrupted", "failed", "needs_attention") and not rows:
                idle += 1
                if idle > 2:
                    yield {"event": "message", "data": RunEvent(seq=last + 1, at=datetime.now(UTC), node="run",
                                                                kind="done", summary=status).model_dump_json()}
                    return
            await asyncio.sleep(0.6)

    return EventSourceResponse(gen(), ping=15)


# ------------------------------------------------------------------ analytics / memory / health

async def analytics(user: UserOut) -> AnalyticsOut:
    uid = user.user_id
    props = await db.fetch("select category, stage, connects_spent from proposals where user_id=%s and stage <> 'drafted'", uid)
    by: dict[str, dict[str, int]] = {}
    for p in props:
        c = by.setdefault(p["category"] or "other", {"n": 0, "r": 0, "h": 0, "c": 0})
        c["n"] += 1
        c["r"] += p["stage"] in ("replied", "interview", "hired")
        c["h"] += p["stage"] == "hired"
        c["c"] += p["connects_spent"] or 0
    n = sum(c["n"] for c in by.values())
    runs = await db.fetch("select graph, tokens, cost_usd, latency_s, status from runs where user_id=%s and latency_s is not null", uid)
    lat = sorted(r["latency_s"] for r in runs if r["latency_s"])
    reasons = await db.fetch("select reason, count(*) as n from feedback where user_id=%s and action in ('reject','skip') "
                             "and reason is not null group by reason order by n desc limit 8", uid)
    jobs = await db.fetchrow("select count(*) filter (where analysis <> '{}') as a, count(*) filter (where risk_score > %s) as s "
                             "from jobs where user_id=%s", config()["thresholds"]["maximum_risk_score"], uid)
    drafted = await db.fetchrow("select count(*) as n from proposals where user_id=%s", uid)
    cost = sum(r["cost_usd"] or 0 for r in runs)
    return AnalyticsOut(
        proposals_sent=n, reply_rate=round(sum(c["r"] for c in by.values()) / n, 3) if n else 0.0,
        hire_rate=round(sum(c["h"] for c in by.values()) / n, 3) if n else 0.0,
        connects_spent=sum(c["c"] for c in by.values()),
        by_category=[CategoryRate(category=k, proposals=v["n"], replies=v["r"], hires=v["h"],
                                  reply_rate=round(v["r"] / v["n"], 3), hire_rate=round(v["h"] / v["n"], 3)) for k, v in by.items()],
        connects_vs_outcomes=[{"label": k, "connects": v["c"], "replies": v["r"], "hires": v["h"]} for k, v in by.items()],
        cost_per_proposal_usd=round(cost / drafted["n"], 4) if drafted["n"] else None,
        p50_latency_s=lat[len(lat) // 2] if lat else None, p95_latency_s=lat[int(len(lat) * 0.95) - 1] if lat else None,
        top_rejection_reasons=[{"label": r["reason"][:80], "count": r["n"]} for r in reasons],
        jobs_analysed=jobs["a"], scams_flagged=jobs["s"])


async def list_memory(user: UserOut) -> MemoryOut:
    items = []
    for ns in ("style", "outcome"):
        for it in await engine.store.asearch((ns, user.user_id), limit=100):
            items.append(MemoryItem(namespace=ns, key=it.key, value=it.value, created_at=it.created_at, updated_at=it.updated_at))
    return MemoryOut(items=items)


async def delete_memory(user: UserOut, namespace: str, key: str) -> None:
    if namespace not in ("style", "outcome"):
        raise HTTPException(404, "unknown namespace")
    await engine.store.adelete((namespace, user.user_id), key)
    if namespace == "style":  # also forget the evidence for it, so it is not re-promoted from old counts
        await engine.store.adelete(("style_candidates", user.user_id), key)


_box_cache: dict[str, Any] = {}


async def _box(user_id: str):
    from agent.mcp_client import ToolBox

    return await ToolBox.http(user_id, new_trace_id())


async def health() -> HealthOut:
    import httpx

    services: list[ServiceStatus] = []
    try:
        await db.fetchrow("select 1")
        services.append(ServiceStatus(name="database", status="ok"))
    except Exception as exc:  # noqa: BLE001
        services.append(ServiceStatus(name="database", status="down", detail=type(exc).__name__))
    for name in ("marketplace", "portfolio", "workspace"):
        url = os.environ.get(f"MCP_{name.upper()}_URL", getattr(settings, f"mcp_{name}_url"))
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.post(url, headers={"Authorization": f"Bearer {os.environ.get('MCP_AUTH_TOKEN', 'dev-mcp-token')}",
                                               "Accept": "application/json, text/event-stream"},
                                 json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            services.append(ServiceStatus(name=f"mcp_{name}", status="ok" if r.status_code < 500 else "down"))
        except Exception as exc:  # noqa: BLE001
            services.append(ServiceStatus(name=f"mcp_{name}", status="down", detail=type(exc).__name__))
    if config()["marketplace"]["mode"] == "gigsim":
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(f"{os.environ.get('GIGSIM_BASE_URL', settings.gigsim_base_url)}/health")
            services.append(ServiceStatus(name="gigsim", status="ok" if r.status_code == 200 else "down"))
        except Exception as exc:  # noqa: BLE001
            services.append(ServiceStatus(name="gigsim", status="down", detail=type(exc).__name__))
    queued = await db.fetchrow("select count(*) as n from work_queue where status='queued'")
    market_down = any(s.status != "ok" for s in services if s.name in ("mcp_marketplace", "gigsim"))
    overall = "down" if services[0].status != "ok" else "degraded" if any(s.status != "ok" for s in services) else "ok"
    if market_down:
        overall = "degraded"
    return HealthOut(status=overall, services=services, queued_while_degraded=queued["n"] if queued else 0)


# ------------------------------------------------------------------ Upwork OAuth (live mode)

async def upwork_oauth_start(user: UserOut) -> RedirectResponse:
    from mcp_servers.marketplace.adapters import upwork_live

    verifier, challenge = upwork_live.pkce_pair()
    state = secrets.token_urlsafe(24)
    await db.execute("insert into oauth_states (state, user_id, verifier) values (%s,%s,%s)", state, user.user_id, verifier)
    url = await upwork_live.authorize_url(settings.public_base_url, settings.upwork_client_id, state, challenge)
    return RedirectResponse(url)


async def upwork_oauth_callback(code: str, state: str) -> RedirectResponse:
    from common.security import encrypt
    from mcp_servers.marketplace.adapters import upwork_live

    row = await db.fetchrow("delete from oauth_states where state=%s and created_at > now() - interval '15 minutes' "
                            "returning user_id, verifier", state)
    if not row:
        return RedirectResponse(f"{settings.public_base_url}/settings?upwork=expired")
    try:
        tokens = await upwork_live.exchange_code(settings.public_base_url, settings.upwork_client_id,
                                                 settings.upwork_client_secret, code, row["verifier"])
    except Exception:  # noqa: BLE001
        return RedirectResponse(f"{settings.public_base_url}/settings?upwork=failed")
    await db.execute("""insert into oauth_tokens (user_id, provider, enc_token) values (%s,'upwork',%s)
                        on conflict (user_id, provider) do update set enc_token=excluded.enc_token, updated_at=now()""",
                     row["user_id"], encrypt(json.dumps(tokens)))
    return RedirectResponse(f"{settings.public_base_url}/settings?upwork=connected")


async def upwork_disconnect(user: UserOut) -> None:
    await db.execute("delete from oauth_tokens where user_id=%s and provider='upwork'", user.user_id)
    p = await _profile(user.user_id)
    if p.get("marketplace_mode") == "upwork_live":
        p["marketplace_mode"] = "gigsim"
        await db.execute("update profiles set data=%s where user_id=%s", json.dumps(p), user.user_id)


def client_metadata() -> dict:
    from mcp_servers.marketplace.adapters import upwork_live

    return upwork_live.client_metadata(settings.public_base_url)


_ = (_serialisable, mirror)
