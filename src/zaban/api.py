import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from zaban.config import settings
from zaban.db import get_db
from zaban.models import Consent, Guardian, Message, Plan, Student, StudentGoal, TutorProfile, TutorSession, new_id, utcnow
from zaban.schemas import (
    ConsentCreate,
    MessageCreate,
    PasswordSet,
    PlacementCreate,
    PIN_PATTERN,
    PlanCreate,
    SessionCreate,
    StudentCreate,
    StudentTokenRequest,
    StudentUpdate,
)
from zaban.security import Auth, get_auth, get_student_for_auth, issue_student_token, require_manager
from zaban.services.ai import tutor_reply
from zaban.models import LearnerDetails
from zaban.services.evaluation import course_note, evaluate_session, past_evaluations
from zaban.services.learner_details import details_out
from zaban.services.settings_store import EXPECTED_OUTPUT_KEY, PROMPT_MODE_DEFAULT, PROMPT_MODE_KEY, get_setting
from zaban.services.curriculum import choose_topic, record_lesson_topic, session_topic, topic_note
from zaban.services.programs import (
    advance_if_done,
    current_item,
    ensure_progress,
    lesson_item_for,
    program_note,
    record_lesson,
    total_items,
)
from zaban.services.learner import get_accent, get_global_prompt, set_learner_profile
from zaban.services.metering import ensure_quota, record_usage
from zaban.services.payments import require_plan
from zaban.services.passwords import hash_password
from zaban.services.progress import build_milestones, cefr_from_score
from zaban.services.sessions import (
    build_system_prompt,
    current_block,
    finish_if_due,
    finish_session,
    guard_message,
)

router = APIRouter()

GUARD_REPLY = "Let's keep our lesson on English. Can you say that in a different way?"


def _require_student_plan(db: DBSession, student: Student) -> None:
    # Children and self-learners need their adult's plan. Students created through a customer's API key are billed to that customer.
    owner_id = student.guardian_id or student.self_owner_id
    if owner_id:
        require_plan(db.get(Guardian, owner_id))


def _require_complete_profile(db: DBSession, student: Student) -> None:
    # A lesson needs the level and the basic facts (age and gender) first, so the prompt is never built from guesses.
    details = db.get(LearnerDetails, student.id)
    missing = []
    if not student.cefr_level:
        missing.append("level")
    if details is None or not details.age:
        missing.append("age")
    if details is None or not details.gender:
        missing.append("gender")
    if missing:
        raise HTTPException(status_code=409, detail="Complete the profile before starting a lesson: " + ", ".join(missing))


def _check_pin_if_guardian(auth: Auth, password: str) -> None:
    if auth.guardian_id and not re.fullmatch(PIN_PATTERN, password):
        raise HTTPException(status_code=400, detail="The PIN must be 4 to 6 digits")


def _student_out(student: Student) -> dict:
    return {
        "id": student.id,
        "external_user_id": student.external_user_id,
        "display_name": student.display_name,
        "username": student.username,
        "age_band": student.age_band,
        "cefr_level": student.cefr_level,
        "has_login": student.password_hash is not None,
    }


def _plan_out(plan: Plan) -> dict:
    return {
        "id": plan.id,
        "goal": plan.goal,
        "months": plan.months,
        "sessions_per_week": plan.sessions_per_week,
        "minutes_per_session": plan.minutes_per_session,
        "start_date": plan.start_date.isoformat(),
        "end_date": plan.end_date.isoformat(),
        "status": plan.status,
        "milestones": plan.milestones,
    }


def _session_out(session: TutorSession, now) -> dict:
    is_active = session.status == "active"
    seconds_left = max(0, int((session.ends_at - now).total_seconds())) if is_active else 0
    return {
        "id": session.id,
        "status": session.status,
        "duration_minutes": session.duration_minutes,
        "started_at": session.started_at.isoformat(),
        "ends_at": session.ends_at.isoformat(),
        "seconds_left": seconds_left,
        "block": current_block(session.started_at, session.ends_at, now) if is_active else "closed",
        "score": session.score,
        "messages": [{"role": m.role, "content": m.content} for m in session.messages],
    }


def _lesson_note(db: DBSession, session_id: str) -> str:
    # The lesson's program item comes first. A curriculum topic is used only when no program fits.
    program_item = lesson_item_for(db, session_id)
    if program_item is not None:
        program, item = program_item
        return program_note(program, item, total_items(db, program.id))
    chosen = session_topic(db, session_id)
    return topic_note(*chosen) if chosen else ""


def _active_plan(db: DBSession, student: Student) -> Plan | None:
    return (
        db.query(Plan)
        .filter(Plan.student_id == student.id, Plan.status == "active")
        .order_by(Plan.start_date.desc())
        .first()
    )


def _has_consent(db: DBSession, student: Student) -> bool:
    return (
        db.query(Consent)
        .filter(Consent.student_id == student.id, Consent.withdrawn_at.is_(None))
        .first()
        is not None
    )


def _require_consent(db: DBSession, student: Student) -> None:
    if not _has_consent(db, student):
        raise HTTPException(status_code=403, detail="Parent consent is required first")


def _get_session_for_auth(db: DBSession, auth: Auth, session_id: str) -> TutorSession:
    session = db.get(TutorSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    get_student_for_auth(db, auth, session.student_id)
    return session


# ---------- Students ----------


@router.post("/students", status_code=201)
def create_student(
    body: StudentCreate,
    auth: Auth = Depends(require_manager),
    db: DBSession = Depends(get_db),
) -> dict:
    external_id = body.external_user_id or f"web-{new_id()}"
    existing = (
        db.query(Student)
        .filter(Student.tenant_id == auth.tenant.id, Student.external_user_id == external_id)
        .first()
    )
    if existing:
        return _student_out(existing)

    if auth.guardian_id and body.age_band == "adult":
        # Adults sign in with their own mobile number and learn for themself. A guardian cannot create them.
        raise HTTPException(status_code=403, detail="Adults must create their own account")
    if auth.guardian_id:
        require_plan(db.get(Guardian, auth.guardian_id))

    username = None
    password_hash = None
    if body.username:
        if not body.password:
            raise HTTPException(status_code=400, detail="A password is needed with a username")
        _check_pin_if_guardian(auth, body.password)
        username = body.username.lower()
        if db.query(Student).filter(Student.username == username).first():
            raise HTTPException(status_code=409, detail="This username is already taken")
        password_hash = hash_password(body.password)

    student = Student(
        tenant_id=auth.tenant.id,
        external_user_id=external_id,
        display_name=body.display_name.strip(),
        username=username,
        password_hash=password_hash,
        guardian_id=auth.guardian_id,
        age_band=body.age_band,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    if body.interests is not None or body.motivation is not None:
        set_learner_profile(db, student.id, interests=body.interests, motivation=body.motivation)
        db.commit()
    if body.goal:
        db.add(StudentGoal(student_id=student.id, goal=body.goal))
        db.commit()
    return _student_out(student)


@router.get("/students")
def list_students(auth: Auth = Depends(require_manager), db: DBSession = Depends(get_db)) -> list[dict]:
    query = db.query(Student).filter(Student.tenant_id == auth.tenant.id)
    if auth.guardian_id:
        query = query.filter(Student.guardian_id == auth.guardian_id)
    return [_student_out(s) for s in query.order_by(Student.created_at).all()]


@router.get("/students/{student_id}")
def get_student(student_id: str, auth: Auth = Depends(get_auth), db: DBSession = Depends(get_db)) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    plan = _active_plan(db, student)
    out = _student_out(student)
    out["has_consent"] = _has_consent(db, student)
    out["active_plan"] = None if plan is None else {"goal": plan.goal, "end_date": plan.end_date.isoformat()}
    return out


@router.patch("/students/{student_id}")
def update_student(
    student_id: str,
    body: StudentUpdate,
    auth: Auth = Depends(require_manager),
    db: DBSession = Depends(get_db),
) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    if body.display_name is not None:
        student.display_name = body.display_name.strip()
    if body.age_band is not None:
        if auth.guardian_id and body.age_band == "adult":
            raise HTTPException(status_code=403, detail="Adults must create their own account")
        student.age_band = body.age_band
    db.commit()
    return _student_out(student)


@router.post("/students/{student_id}/password")
def set_student_password(
    student_id: str,
    body: PasswordSet,
    auth: Auth = Depends(require_manager),
    db: DBSession = Depends(get_db),
) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    if not student.username:
        raise HTTPException(status_code=400, detail="This student has no login")
    _check_pin_if_guardian(auth, body.password)
    student.password_hash = hash_password(body.password)
    # A new PIN ends old child sessions and clears any lock from wrong attempts.
    student.session_version += 1
    student.failed_logins = 0
    student.locked_until = None
    db.commit()
    return {"ok": True}


@router.delete("/students/{student_id}", status_code=204)
def delete_student(
    student_id: str,
    auth: Auth = Depends(require_manager),
    db: DBSession = Depends(get_db),
) -> Response:
    student = get_student_for_auth(db, auth, student_id)
    db.delete(student)
    db.commit()
    return Response(status_code=204)


@router.post("/auth/student-token")
def create_student_token(
    body: StudentTokenRequest,
    auth: Auth = Depends(require_manager),
    db: DBSession = Depends(get_db),
) -> dict:
    student = get_student_for_auth(db, auth, body.student_id)
    return {"token": issue_student_token(student), "expires_in": settings.session_token_ttl_seconds}


@router.post("/students/{student_id}/consent", status_code=201)
def give_consent(
    student_id: str,
    body: ConsentCreate,
    auth: Auth = Depends(require_manager),
    db: DBSession = Depends(get_db),
) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    if not body.accepted:
        raise HTTPException(status_code=400, detail="Consent must be accepted")
    consent = Consent(student_id=student.id, text_version=body.text_version)
    db.add(consent)
    db.commit()
    return {"id": consent.id, "accepted_at": consent.accepted_at.isoformat()}


@router.post("/students/{student_id}/placement")
def set_placement(
    student_id: str,
    body: PlacementCreate,
    auth: Auth = Depends(require_manager),
    db: DBSession = Depends(get_db),
) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    student.cefr_level = body.level if body.level else cefr_from_score(body.score)
    db.commit()
    return _student_out(student)


@router.post("/students/{student_id}/plans", status_code=201)
def create_plan(
    student_id: str,
    body: PlanCreate,
    auth: Auth = Depends(require_manager),
    db: DBSession = Depends(get_db),
) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    _require_consent(db, student)
    for old in db.query(Plan).filter(Plan.student_id == student.id, Plan.status == "active"):
        old.status = "replaced"
    start = utcnow()
    plan = Plan(
        student_id=student.id,
        goal=body.goal,
        months=body.months,
        sessions_per_week=body.sessions_per_week,
        minutes_per_session=body.minutes_per_session,
        start_date=start,
        end_date=start + timedelta(days=30 * body.months),
        milestones=build_milestones(body.months),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _plan_out(plan)


@router.get("/students/{student_id}/usage")
def student_usage(student_id: str, auth: Auth = Depends(get_auth), db: DBSession = Depends(get_db)) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    sessions = db.query(TutorSession).filter(TutorSession.student_id == student.id).all()
    for session in sessions:
        finish_if_due(session, utcnow())
    db.commit()
    finished = [s for s in sessions if s.status == "completed"]
    last = max((s.started_at for s in sessions), default=None)
    plan = _active_plan(db, student)
    return {
        "lessons_completed": len(finished),
        "minutes_used": sum(s.duration_minutes for s in finished),
        "last_lesson_at": last.isoformat() if last else None,
        "plan_end_date": plan.end_date.isoformat() if plan else None,
    }


# ---------- Sessions ----------


@router.get("/students/{student_id}/sessions/active")
def active_session(student_id: str, auth: Auth = Depends(get_auth), db: DBSession = Depends(get_db)) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    now = utcnow()
    session = (
        db.query(TutorSession)
        .filter(TutorSession.student_id == student.id, TutorSession.status == "active")
        .order_by(TutorSession.started_at.desc())
        .first()
    )
    if session is None:
        return {"session": None}
    finish_if_due(session, now)
    db.commit()
    if session.status != "active":
        return {"session": None}
    return {"session": _session_out(session, now)}


@router.post("/students/{student_id}/sessions", status_code=201)
def start_session(
    student_id: str,
    body: SessionCreate,
    auth: Auth = Depends(get_auth),
    db: DBSession = Depends(get_db),
) -> dict:
    student = get_student_for_auth(db, auth, student_id)
    _require_consent(db, student)
    _require_student_plan(db, student)
    _require_complete_profile(db, student)
    ensure_quota(auth.tenant)

    now = utcnow()
    for old in db.query(TutorSession).filter(TutorSession.student_id == student.id, TutorSession.status == "active"):
        finish_if_due(old, now)
        if old.status == "active":
            raise HTTPException(status_code=409, detail="A lesson is already running")

    progress = ensure_progress(db, student)
    if progress is not None:
        advance_if_done(db, student.id)
        db.commit()
        if progress.status == "waiting_approval":
            raise HTTPException(status_code=409, detail="This block of lessons is finished and waits for approval")
        if progress.status == "finished":
            raise HTTPException(status_code=409, detail="This program is finished")

    plan = _active_plan(db, student)
    # A learning program decides the lesson when one fits. Otherwise the curriculum topic is used.
    chosen = None if progress is not None else choose_topic(db, student, body.topic_id)
    if body.topic_id and progress is None and chosen is None:
        raise HTTPException(status_code=400, detail="No written version of this topic fits this learner's age and level")
    session = TutorSession(
        student_id=student.id,
        plan_id=plan.id if plan else None,
        duration_minutes=body.duration_minutes,
        started_at=now,
        ends_at=now + timedelta(minutes=body.duration_minutes),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    out = _session_out(session, now)
    out["topic"] = None
    out["program"] = None
    if progress is not None:
        item = current_item(db, progress)
        if item is not None:
            record_lesson(db, session.id, progress, item)
            db.commit()
            out["program"] = {"title": item.title, "position": item.position + 1, "total": total_items(db, progress.program_id)}
    if chosen:
        topic, variant = chosen
        record_lesson_topic(db, session.id, topic, variant)
        db.commit()
        out["topic"] = {"id": topic.id, "title": topic.title, "variant": variant.id}
    return out


@router.get("/sessions/{session_id}")
def get_session(session_id: str, auth: Auth = Depends(get_auth), db: DBSession = Depends(get_db)) -> dict:
    session = _get_session_for_auth(db, auth, session_id)
    now = utcnow()
    finish_if_due(session, now)
    db.commit()
    evaluate_session(db, session)
    return _session_out(session, now)


@router.post("/sessions/{session_id}/messages")
def send_message(
    session_id: str,
    body: MessageCreate,
    auth: Auth = Depends(get_auth),
    db: DBSession = Depends(get_db),
) -> dict:
    session = _get_session_for_auth(db, auth, session_id)
    student = get_student_for_auth(db, auth, session.student_id)
    now = utcnow()
    finish_if_due(session, now)
    if session.status != "active":
        db.commit()
        raise HTTPException(status_code=409, detail="This lesson is closed")
    ensure_quota(auth.tenant)

    text = body.content.strip()
    block = current_block(session.started_at, session.ends_at, now)
    reason = guard_message(text)
    if reason:
        # Off-topic or unsafe input never reaches the model. It is still stored so reports can show it.
        db.add(Message(session_id=session.id, role="user", content=text))
        db.add(Message(session_id=session.id, role="assistant", content=GUARD_REPLY))
        db.commit()
        return {"reply": GUARD_REPLY, "block": block, "guarded": reason, "mode": None, "seconds_left": None}

    history = [{"role": m.role, "content": m.content} for m in session.messages]
    history.append({"role": "user", "content": text})
    system_prompt = build_system_prompt(
        student,
        _active_plan(db, student),
        block,
        session.duration_minutes,
        get_global_prompt(db),
        db.get(TutorProfile, student.id),
        get_accent(db, student.id),
        _lesson_note(db, session.id),
        details=db.get(LearnerDetails, student.id),
        mode=get_setting(db, PROMPT_MODE_KEY, PROMPT_MODE_DEFAULT),
        expected_output=get_setting(db, EXPECTED_OUTPUT_KEY),
        past_notes=past_evaluations(db, student.id),
        course_note=course_note(db, student),
    )
    reply = tutor_reply(system_prompt, history)

    db.add(Message(session_id=session.id, role="user", content=text))
    db.add(Message(session_id=session.id, role="assistant", content=reply.text))
    record_usage(db, auth.tenant, session.id, reply.input_tokens, reply.output_tokens)
    db.commit()
    seconds_left = max(0, int((session.ends_at - now).total_seconds()))
    return {
        "reply": reply.text,
        "block": block,
        "guarded": None,
        "mode": reply.mode,
        "seconds_left": seconds_left,
    }


@router.post("/sessions/{session_id}/end")
def end_session(session_id: str, auth: Auth = Depends(get_auth), db: DBSession = Depends(get_db)) -> dict:
    session = _get_session_for_auth(db, auth, session_id)
    now = utcnow()
    if session.status == "active":
        finish_session(session, now)
    db.commit()
    return _session_out(session, now)
