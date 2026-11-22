from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from zaban.services.skill_levels import levels_out
from zaban.db import get_db
from zaban.models import Guardian, Message, Plan, SelfTest, SelfTestMessage, Student, Tenant, TutorSession, Usage, utcnow
from zaban.security import Auth, get_auth, get_student_for_auth, require_manager, require_tenant
from zaban.services.curriculum import session_topic
from zaban.services.progress import actual_percent, planned_percent, progress_status
from zaban.services.sessions import finish_if_due
from zaban.services.partner_budget import reserve_reached
from zaban.services.partner_end import finish_partner_session
from zaban.services.partner_selftest import run_test_update
from zaban.services.partner_settings import partner_value
from zaban.services.payments import has_active_plan

router = APIRouter()

SUGGESTIONS = {
    "insufficient_data": "Complete at least 3 lessons so progress can be measured.",
    "ahead": "Consider a harder topic or a shorter plan.",
    "on_track": "Keep the current pace.",
    "behind": "Review mistakes from the last 3 lessons and add one short extra lesson this week.",
    "well_behind": "Review the plan and check the starting level.",
    "no_plan": "Create a plan to start tracking progress.",
}

SUMMARIES_FA = {
    "insufficient_data": "هنوز جلسه‌ی کافی برای ارزیابی پیشرفت ثبت نشده است.",
    "ahead": "پیشرفت شما از برنامه جلوتر است.",
    "on_track": "پیشرفت شما طبق برنامه است.",
    "behind": "پیشرفت کمی از برنامه عقب است و راهکار پیشنهادی آماده است.",
    "well_behind": "پیشرفت فاصله‌ی قابل توجهی با برنامه دارد. پیشنهاد می‌کنیم برنامه بازبینی شود.",
    "no_plan": "هنوز برنامه‌ای برای شما ثبت نشده است.",
}


def _snapshot(db: DBSession, student: Student) -> tuple[Plan | None, dict]:
    now = utcnow()
    plan = (
        db.query(Plan)
        .filter(Plan.student_id == student.id, Plan.status == "active")
        .order_by(Plan.start_date.desc())
        .first()
    )
    if plan is None:
        return None, {"status": "no_plan", "planned_percent": None, "actual_percent": None}

    sessions = db.query(TutorSession).filter(TutorSession.plan_id == plan.id).order_by(TutorSession.started_at).all()
    for session in sessions:
        finish_if_due(session, now)
    planned = planned_percent(plan, now)
    actual = actual_percent(sessions)
    return plan, {
        "status": progress_status(planned, actual),
        "planned_percent": planned,
        "actual_percent": actual,
        "completed_sessions": sum(1 for s in sessions if s.status == "completed"),
    }


def _session_rows(db: DBSession, student: Student) -> list[dict]:
    sessions = (
        db.query(TutorSession)
        .filter(TutorSession.student_id == student.id, TutorSession.status != "cancelled")
        .order_by(TutorSession.started_at.desc())
        .limit(20)
        .all()
    )
    rows = []
    for s in sessions:
        # A lesson on a curriculum topic is titled with that topic. A free talk has no topic.
        found = session_topic(db, s.id)
        rows.append(
            {
                "id": s.id,
                "lesson_number": None,
                "lesson_title": found[0].title if found else None,
                "lesson_title_en": None,
                "started_at": s.started_at.isoformat(),
                "duration_minutes": s.duration_minutes,
                "status": s.status,
                "score": s.score,
            }
        )
    return rows


SKILL_FA = {"writing": "نوشتن", "listening": "شنیدن", "speaking": "گفتن", "mixed": "ترکیبی"}


def _levels(row: TutorSession | SelfTest) -> dict:
    return {
        "range": row.eval_range,
        "accuracy": row.eval_accuracy,
        "fluency": row.eval_fluency,
        "interaction": row.eval_interaction,
        "coherence": row.eval_coherence,
    }


# The state of a report: "active" (still running), "completed" (evaluated) or "unevaluated" (finished, no evaluation yet).
def _session_state(s: TutorSession) -> str:
    if s.status == "active":
        return "active"
    return "completed" if s.end_status == "evaluated" else "unevaluated"


def _test_state(t: SelfTest) -> str:
    if t.status != "finished":
        return "active"
    # Tests from before the conversation partner have no evaluation of their own; they count as completed.
    return "completed" if t.partner_status in ("", "evaluated") else "unevaluated"


def _session_item(db: DBSession, s: TutorSession) -> dict:
    # A free talk has no curriculum topic, so it is listed under its own type and title.
    if s.session_kind == "lesson":
        found = session_topic(db, s.id)
        kind, title = "lesson", found[0].title if found else "جلسه"
    else:
        # A free talk is titled with its topic after the name, for example «گفتگوی آزاد سفر به شمال».
        kind, title = "talk", " ".join(part for part in ("گفتگوی آزاد", s.topic) if part)
    return {
        "type": kind,
        "id": s.id,
        "title": title,
        "date": s.started_at.isoformat(),
        "duration_minutes": s.duration_minutes,
        "status": s.status,
        "state": _session_state(s),
        "score": s.score,
        "levels": _levels(s),
        "text": s.evaluation,
    }


def _test_item(t: SelfTest) -> dict:
    return {
        "type": "test",
        "id": t.id,
        "title": f"آزمون: {SKILL_FA.get(t.skill, t.skill)}",
        "date": t.created_at.isoformat(),
        "duration_minutes": t.minutes,
        "status": t.status,
        "state": _test_state(t),
        "score": t.score,
        "levels": _levels(t),
        "text": t.result,
    }


# The report kinds the learner can open: "lesson", "talk" (free talk) and "test". "all" gives every kind together.
REPORT_KINDS = ("all", "lesson", "talk", "test")
SESSION_KIND_OF = {"lesson": "lesson", "talk": "free"}


def report_items_out(db: DBSession, student: Student, kind: str = "all") -> dict:
    # One list of reports, newest first. The list holds one kind when a kind is asked for.
    sessions = []
    if kind in ("all", "lesson", "talk"):
        query = db.query(TutorSession).filter(TutorSession.student_id == student.id, TutorSession.status != "cancelled")
        if kind != "all":
            query = query.filter(TutorSession.session_kind == SESSION_KIND_OF[kind])
        sessions = query.order_by(TutorSession.started_at.desc()).limit(50).all()
    tests = []
    if kind in ("all", "test"):
        tests = (
            db.query(SelfTest)
            .filter(SelfTest.student_id == student.id, SelfTest.status != "cancelled")
            .order_by(SelfTest.created_at.desc())
            .limit(50)
            .all()
        )
    items = [_session_item(db, s) for s in sessions] + [_test_item(t) for t in tests]
    items.sort(key=lambda item: item["date"], reverse=True)
    return {"items": items[:50]}


@router.get("/students/{student_id}/reports/items")
def report_items(
    student_id: str,
    kind: str = "all",
    auth: Auth = Depends(get_auth),
    db: DBSession = Depends(get_db),
) -> dict:
    if kind not in REPORT_KINDS:
        raise HTTPException(status_code=400, detail="Unknown report kind")
    student = get_student_for_auth(db, auth, student_id)
    out = report_items_out(db, student, kind)
    db.commit()
    return out


@router.get("/students/{student_id}/reports/{item_type}/{item_id}/messages")
def report_messages(
    student_id: str,
    item_type: str,
    item_id: str,
    auth: Auth = Depends(get_auth),
    db: DBSession = Depends(get_db),
) -> dict:
    # The conversation of one report: the learner's messages and the teacher's, in order. Only the learner's own reports.
    student = get_student_for_auth(db, auth, student_id)
    if item_type in ("lesson", "talk"):
        session = db.get(TutorSession, item_id)
        if session is None or session.student_id != student.id:
            raise HTTPException(status_code=404, detail="Report not found")
        rows = db.query(Message).filter(Message.session_id == session.id).order_by(Message.id).all()
    elif item_type == "test":
        test = db.get(SelfTest, item_id)
        if test is None or test.student_id != student.id:
            raise HTTPException(status_code=404, detail="Report not found")
        rows = db.query(SelfTestMessage).filter(SelfTestMessage.test_id == test.id).order_by(SelfTestMessage.id).all()
    else:
        raise HTTPException(status_code=400, detail="Unknown report kind")
    messages = [{"role": row.role, "content": row.content} for row in rows if row.role in ("user", "assistant")]
    return {"messages": messages}


@router.post("/students/{student_id}/reports/{item_type}/{item_id}/evaluate")
def evaluate_report(
    student_id: str,
    item_type: str,
    item_id: str,
    auth: Auth = Depends(get_auth),
    db: DBSession = Depends(get_db),
) -> dict:
    # Makes the evaluation of an unevaluated report now. The answer says what happened: "completed", "impossible"
    # (too few messages to judge), "plan" (the plan has no tokens left for it) or "failed" (the model could not be reached).
    student = get_student_for_auth(db, auth, student_id)
    owner = db.get(Guardian, student.self_owner_id) if student.self_owner_id else None
    min_messages = int(partner_value(db, "partner_min_messages_eval"))
    if owner is not None and (not has_active_plan(owner) or reserve_reached(db, owner)):
        return {"state": "plan"}
    if item_type in ("lesson", "talk"):
        session = db.get(TutorSession, item_id)
        if session is None or session.student_id != student.id:
            raise HTTPException(status_code=404, detail="Report not found")
        if session.status == "active":
            raise HTTPException(status_code=409, detail="This report is still running")
        if _session_state(session) == "completed":
            return {"state": "completed"}
        turns = db.query(Message).filter(Message.session_id == session.id, Message.role == "user").count()
        if turns < min_messages:
            return {"state": "impossible"}
        session.end_status = "pending"
        session.end_attempts = 0
        db.commit()
        finish_partner_session(db, session)
        db.commit()
        return {"state": "completed" if session.end_status == "evaluated" else "failed"}
    if item_type == "test":
        test = db.get(SelfTest, item_id)
        if test is None or test.student_id != student.id:
            raise HTTPException(status_code=404, detail="Report not found")
        if test.status != "finished":
            raise HTTPException(status_code=409, detail="This report is still running")
        if _test_state(test) == "completed":
            return {"state": "completed"}
        turns = db.query(SelfTestMessage).filter(SelfTestMessage.test_id == test.id, SelfTestMessage.role == "user").count()
        if turns < min_messages:
            return {"state": "impossible"}
        test.partner_status = "pending"
        test.partner_attempts = 0
        db.commit()
        run_test_update(db, student, test, utcnow())
        db.commit()
        return {"state": "completed" if test.partner_status == "evaluated" else "failed"}
    raise HTTPException(status_code=400, detail="Unknown report kind")


@router.get("/students/{student_id}/reports/progress")
def student_progress(student_id: str, auth: Auth = Depends(get_auth), db: DBSession = Depends(get_db)) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    plan, snapshot = _snapshot(db, student)
    db.commit()
    return {
        "student_id": student.id,
        "levels": levels_out(student),
        "plan": None if plan is None else {"goal": plan.goal, "end_date": plan.end_date.isoformat()},
        **snapshot,
        "milestones": plan.milestones if plan else [],
        "suggestion": SUGGESTIONS[snapshot["status"]],
        "sessions": _session_rows(db, student),
    }


@router.get("/students/{student_id}/reports/summary")
def summary_report(
    student_id: str,
    auth: Auth = Depends(require_manager),
    db: DBSession = Depends(get_db),
) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    plan, snapshot = _snapshot(db, student)
    db.commit()
    return {
        "student_id": student.id,
        "levels": levels_out(student),
        **snapshot,
        "milestones": plan.milestones if plan else [],
        "summary_fa": SUMMARIES_FA[snapshot["status"]],
        "suggestion": SUGGESTIONS[snapshot["status"]],
    }


@router.get("/tenant/usage")
def tenant_usage(tenant: Tenant = Depends(require_tenant), db: DBSession = Depends(get_db)) -> dict:
    input_total, output_total, cost_total = (
        db.query(
            func.coalesce(func.sum(Usage.input_tokens), 0),
            func.coalesce(func.sum(Usage.output_tokens), 0),
            func.coalesce(func.sum(Usage.cost_usd), 0.0),
        )
        .filter(Usage.tenant_id == tenant.id)
        .one()
    )
    return {
        "tenant": tenant.name,
        "status": tenant.status,
        "quota_tokens": tenant.quota_tokens,
        "used_tokens": tenant.used_tokens,
        "remaining_tokens": max(0, tenant.quota_tokens - tenant.used_tokens),
        "expires_at": tenant.expires_at.isoformat() if tenant.expires_at else None,
        "input_tokens": int(input_total),
        "output_tokens": int(output_total),
        "estimated_cost_usd": round(float(cost_total), 6),
    }
