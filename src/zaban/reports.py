from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from zaban.db import get_db
from zaban.models import Plan, Student, Tenant, TutorSession, Usage, utcnow
from zaban.security import Auth, get_auth, get_student_for_auth, require_manager, require_tenant
from zaban.services.programs import lesson_item_for
from zaban.services.progress import actual_percent, planned_percent, progress_status
from zaban.services.sessions import finish_if_due

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
    "ahead": "پیشرفت فرزندتان از برنامه جلوتر است.",
    "on_track": "پیشرفت فرزندتان طبق برنامه است.",
    "behind": "پیشرفت کمی از برنامه عقب است و راهکار پیشنهادی آماده است.",
    "well_behind": "پیشرفت فاصله‌ی قابل توجهی با برنامه دارد. پیشنهاد می‌کنیم برنامه بازبینی شود.",
    "no_plan": "هنوز برنامه‌ای برای فرزندتان ثبت نشده است.",
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
        .filter(TutorSession.student_id == student.id)
        .order_by(TutorSession.started_at.desc())
        .limit(20)
        .all()
    )
    rows = []
    for s in sessions:
        # A lesson of the learning program is titled with its program item. A free talk has no program item.
        found = lesson_item_for(db, s.id)
        title = f"جلسه {found[1].position + 1}: {found[1].title}" if found else "گفتگوی آزاد با Niko"
        rows.append(
            {
                "id": s.id,
                "title": title,
                "started_at": s.started_at.isoformat(),
                "duration_minutes": s.duration_minutes,
                "status": s.status,
                "score": s.score,
            }
        )
    return rows


@router.get("/students/{student_id}/reports/progress")
def student_progress(student_id: str, auth: Auth = Depends(get_auth), db: DBSession = Depends(get_db)) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    plan, snapshot = _snapshot(db, student)
    db.commit()
    return {
        "student_id": student.id,
        "cefr_level": student.cefr_level,
        "plan": None if plan is None else {"goal": plan.goal, "end_date": plan.end_date.isoformat()},
        **snapshot,
        "milestones": plan.milestones if plan else [],
        "suggestion": SUGGESTIONS[snapshot["status"]],
        "sessions": _session_rows(db, student),
    }


@router.get("/students/{student_id}/reports/parent")
def parent_report(
    student_id: str,
    auth: Auth = Depends(require_manager),
    db: DBSession = Depends(get_db),
) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    plan, snapshot = _snapshot(db, student)
    db.commit()
    return {
        "student_id": student.id,
        "cefr_level": student.cefr_level,
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
