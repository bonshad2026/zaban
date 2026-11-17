from datetime import timedelta

from pydantic import BaseModel, Field

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
    PlanCreate,
    SessionCreate,
    StudentCreate,
    StudentTokenRequest,
    StudentUpdate,
)
from zaban.security import Auth, get_auth, get_student_for_auth, issue_student_token, require_manager
from zaban.services.ai import tutor_reply
from zaban.services.partner_output import parse_output
from zaban.services.partner_prompt import build_prompt, mode_part, sentence_seconds, turn_block
from zaban.services.partner_rhythm import move as move_rhythm, segment_state, set_rhythm, start_rhythm
from zaban.services.partner_settings import partner_value
from zaban.services.partner_turns import apply_turn
from zaban.services.partner_budget import reserve_reached, warnings as budget_warnings
from zaban.services.partner_end import finish_partner_session, retry_pending
from zaban.models import LearnerDetails
from zaban.services.evaluation import course_note, evaluate_session, past_evaluations, score_pending_sessions
from zaban.services.learner_details import details_out, save_details
from zaban.services.settings_store import EXPECTED_OUTPUT_KEY, PROMPT_MODE_DEFAULT, PROMPT_MODE_KEY, get_setting
from zaban.services.curriculum import choose_topic, record_lesson_topic, session_topic, topic_note
from zaban.services.learner import get_accent, get_global_prompt, set_learner_profile
from zaban.services.metering import ensure_quota, record_usage
from zaban.services.payments import charge_plan_tokens, has_active_plan, require_plan
from zaban.services.prompt_template import has_saved_template, learner_values, render, get_template
from zaban.services.sessions import finish_session
from zaban.services.passwords import hash_password
from zaban.services.progress import build_milestones, cefr_from_score
from zaban.services.sessions import (
    block_line,
    build_system_prompt,
    compose_start_prompt,
    current_block,
    finish_if_due,
    finish_session,
    guard_message,
    join_prompt,
)

# Shown to the learner when the adult's plan has no tokens left. The lesson closes after it.
PLAN_USED_NOTICE = "توکن‌های پلن شما تمام شده و این کلاس همین‌جا بسته می‌شود. برای ادامه، پلن جدید تهیه کنید."

router = APIRouter()

GUARD_REPLY = "Let's keep our lesson on English. Can you say that in a different way?"


def _require_student_plan(db: DBSession, student: Student) -> None:
    # Adults who learn for themself need their own plan. Students created through a customer's API key are billed to that customer.
    owner_id = student.self_owner_id
    if owner_id:
        require_plan(db.get(Guardian, owner_id))


def _require_complete_profile(db: DBSession, student: Student) -> None:
    # A lesson needs the level and the basic facts (age and gender) first, so the prompt is never built from guesses.
    details = db.get(LearnerDetails, student.id)
    if student.self_owner_id and (details is None or not details.age or not details.gender):
        # An adult who learns for themself enters age and gender in the account. Copy them to the learner details once,
        # so the lesson prompt sees them too. Without this, a complete account still could not start a lesson.
        adult = db.get(Guardian, student.self_owner_id)
        values = {}
        if adult and adult.age and (details is None or not details.age):
            values["age"] = adult.age
        if adult and adult.gender and (details is None or not details.gender):
            values["gender"] = adult.gender
        if values:
            details = save_details(db, student.id, values)
            db.commit()
    missing = []
    if not student.cefr_level:
        missing.append("level")
    if details is None or not details.age:
        missing.append("age")
    if details is None or not details.gender:
        missing.append("gender")
    if missing:
        raise HTTPException(status_code=409, detail="Complete the profile before starting a lesson: " + ", ".join(missing))


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
    chosen = session_topic(db, session_id)
    return topic_note(*chosen) if chosen else ""


def _start_parts(db: DBSession, student: Student, session: TutorSession) -> dict[str, str]:
    # Each source is read from the database here, so the prompt matches what the learner and administrator set.
    return compose_start_prompt(
        student,
        _active_plan(db, student),
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
        raise HTTPException(status_code=403, detail="Consent is required first")


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

    username = None
    password_hash = None
    if body.username:
        if not body.password:
            raise HTTPException(status_code=400, detail="A password is needed with a username")
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
    student.password_hash = hash_password(body.password)
    # A new password ends old learner sessions and clears any lock from wrong attempts.
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

    score_pending_sessions(db, student.id)
    retry_pending(db, student.id)

    plan = _active_plan(db, student)
    # The next topic of the lesson path decides the lesson, unless the learner asked to play a finished topic again.
    chosen = choose_topic(db, student, body.topic_id)
    if body.topic_id and chosen is None:
        raise HTTPException(status_code=400, detail="This topic does not exist")
    if chosen and student.repeat_topic_id:
        # The repeat request is used up by this lesson.
        student.repeat_topic_id = None
    session = TutorSession(
        student_id=student.id,
        plan_id=plan.id if plan else None,
        duration_minutes=body.duration_minutes,
        started_at=now,
        ends_at=now + timedelta(minutes=body.duration_minutes),
        engine=partner_value(db, "partner_engine"),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    out = _session_out(session, now)
    out["topic"] = None
    out["program"] = None
    if chosen:
        topic, variant = chosen
        record_lesson_topic(db, session.id, topic, variant)
        db.commit()
        out["topic"] = {"id": topic.id, "title": topic.title, "variant": variant.id if variant else None}
    # The start prompt is composed once here and sent as the first input of every reply in this lesson.
    if partner_value(db, "partner_engine") == "new":
        # The conversation partner builds its own five-part prompt once, when the lesson starts (section 7.1).
        session.start_prompt = build_prompt(db, student)
        start_rhythm(db, session, now)
    elif has_saved_template(db):
        # The administrator's template is filled with this learner's stored values, once, at the start of the lesson.
        session.start_prompt, _ = render(get_template(db), learner_values(db, student, session.duration_minutes))
    else:
        session.start_prompt = join_prompt(_start_parts(db, student, session))
    db.commit()
    return out


@router.get("/sessions/{session_id}")
def get_session(session_id: str, auth: Auth = Depends(get_auth), db: DBSession = Depends(get_db)) -> dict:
    session = _get_session_for_auth(db, auth, session_id)
    now = utcnow()
    finish_if_due(session, now)
    db.commit()
    _evaluate_finished(db, session)
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
    # The adult who pays for this learner must still have a plan with tokens left. If not, the lesson closes here.
    owner_id = student.self_owner_id
    owner = db.get(Guardian, owner_id) if owner_id else None
    partner_lesson = session.engine == "new"
    if owner is not None and (not has_active_plan(owner) or (partner_lesson and reserve_reached(db, owner))):
        finish_session(session, now)
        db.commit()
        if partner_lesson:
            finish_partner_session(db, session)
        return {"reply": PLAN_USED_NOTICE, "block": None, "guarded": None, "mode": "closed", "seconds_left": 0,
                "closed": True, "notice": PLAN_USED_NOTICE, "warnings": []}

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
    if session.start_prompt:
        system_prompt = session.start_prompt + "\n\n" + block_line(block, session.duration_minutes)
    else:
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
    partner = None
    rhythm = None
    if session.engine == "new" and session.start_prompt:
        # The partner answers in JSON. Only a valid answer is shown as a reply and written to the learner's record.
        # Free conversation has no time and no rhythm. A lesson uses the part of its rhythm that is running now.
        free = session.session_kind == "free"
        if free:
            mode, seconds, sentence = "conversation", None, None
        else:
            rhythm = segment_state(session, now)
            mode, seconds = rhythm["mode"], rhythm["seconds_left"]
            sentence = sentence_seconds(db, student) if mode == "translation" else None
        partner_prompt = session.start_prompt + "\n\n" + mode_part(db, mode, free, student).text + "\n\n" + turn_block(mode, block, seconds, sentence)
        reply = tutor_reply(partner_prompt, history)
        turn = parse_output(reply.text)
        if turn.valid:
            apply_turn(db, student, session.id, turn, text, now)
        partner = {"valid": turn.valid, "feedback": turn.feedback, "new_phrase": turn.new_phrase, "next_action": turn.next_action}
        shown = turn.reply
    else:
        reply = tutor_reply(system_prompt, history)
        shown = reply.text

    db.add(Message(session_id=session.id, role="user", content=text))
    db.add(Message(session_id=session.id, role="assistant", content=reply.text))
    record_usage(db, auth.tenant, session.id, reply.input_tokens, reply.output_tokens)
    closed = False
    if owner is not None:
        charge_plan_tokens(db, owner, reply.input_tokens + reply.output_tokens)
        # When the last tokens are used, the lesson ends after this reply.
        closed = not has_active_plan(owner) or (partner_lesson and reserve_reached(db, owner))
    if closed:
        finish_session(session, now)
    db.commit()
    if closed and partner_lesson:
        # The end routine runs now, with the tokens kept back for it (section 13.7).
        finish_partner_session(db, session)
    seconds_left = max(0, int((session.ends_at - now).total_seconds()))
    return {
        "reply": shown,
        "block": block,
        "guarded": None,
        "mode": reply.mode,
        "seconds_left": seconds_left,
        "closed": closed,
        "notice": PLAN_USED_NOTICE if closed else None,
        "partner": partner,
        "warnings": budget_warnings(db, owner, now) if partner_lesson else [],
        "rhythm": _rhythm_out(rhythm) if rhythm else None,
    }


class RhythmPart(BaseModel):
    mode: str = Field(max_length=20)
    minutes: int


class RhythmUpdate(BaseModel):
    parts: list[RhythmPart] = Field(max_length=8)


class RhythmMove(BaseModel):
    # "current" starts this part again, "next" goes to the part after it, or a mode name jumps to that part.
    to: str = Field(min_length=1, max_length=20)


def _rhythm_out(state: dict) -> dict:
    return {
        "mode": state["mode"],
        "label": state["label"],
        "seconds_left": state["seconds_left"],
        "over": state["over"],
        "next_mode": state["next_mode"],
        "parts": state["parts"],
        "index": state.get("index", 0),
    }


@router.post("/students/{student_id}/free-conversation", status_code=201)
def start_free_conversation(
    student_id: str,
    auth: Auth = Depends(get_auth),
    db: DBSession = Depends(get_db),
) -> dict:
    # Free conversation (section 4.1): no time, no rhythm and no step in the curriculum. It always uses the conversation partner.
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
    plan = _active_plan(db, student)
    session = TutorSession(
        student_id=student.id,
        plan_id=plan.id if plan else None,
        duration_minutes=0,
        started_at=now,
        ends_at=now + timedelta(hours=24),
        session_kind="free",
        engine="new",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    session.start_prompt = build_prompt(db, student)
    db.commit()
    return _session_out(session, now)


@router.get("/sessions/{session_id}/rhythm")
def get_rhythm(session_id: str, auth: Auth = Depends(get_auth), db: DBSession = Depends(get_db)) -> dict:
    session = _get_session_for_auth(db, auth, session_id)
    if session.engine != "new" or session.session_kind == "free":
        return {"rhythm": None}
    return _rhythm_out(segment_state(session, utcnow()))


@router.post("/sessions/{session_id}/rhythm/move")
def move_lesson_rhythm(
    session_id: str,
    body: RhythmMove,
    auth: Auth = Depends(get_auth),
    db: DBSession = Depends(get_db),
) -> dict:
    session = _get_session_for_auth(db, auth, session_id)
    now = utcnow()
    if session.status != "active" or session.session_kind == "free":
        raise HTTPException(status_code=409, detail="This lesson is closed or has no rhythm")
    try:
        move_rhythm(session, now, body.to)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    db.commit()
    return _rhythm_out(segment_state(session, now))


@router.put("/sessions/{session_id}/rhythm")
def set_lesson_rhythm(
    session_id: str,
    body: RhythmUpdate,
    auth: Auth = Depends(get_auth),
    db: DBSession = Depends(get_db),
) -> dict:
    session = _get_session_for_auth(db, auth, session_id)
    now = utcnow()
    if session.status != "active" or session.session_kind == "free":
        raise HTTPException(status_code=409, detail="This lesson is closed or has no rhythm")
    try:
        set_rhythm(session, now, [part.model_dump() for part in body.parts])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    db.commit()
    return _rhythm_out(segment_state(session, now))


def _evaluate_finished(db: DBSession, session: TutorSession) -> None:
    # The conversation partner's end routine for its lessons, the old evaluation for the rest.
    if session.engine == "new":
        finish_partner_session(db, session)
    else:
        evaluate_session(db, session)


@router.post("/sessions/{session_id}/end")
def end_session(session_id: str, auth: Auth = Depends(get_auth), db: DBSession = Depends(get_db)) -> dict:
    session = _get_session_for_auth(db, auth, session_id)
    now = utcnow()
    if session.status == "active":
        finish_session(session, now)
    db.commit()
    # Score the lesson now, so the learner sees it at once. If the model cannot be reached, the score is made later.
    try:
        _evaluate_finished(db, session)
    except Exception:
        db.rollback()
    return _session_out(session, now)
