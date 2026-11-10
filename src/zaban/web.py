from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session as DBSession

from zaban.config import settings
from zaban.db import get_db
from zaban.models import Consent, Guardian, LearningProgram, ProgramItem, Student, Tenant, VoiceSample, WebSession, utcnow
from zaban.schemas import AccentChoice, LevelTestAnswers, OtpRequest, PasswordReset, SignUpCreate, UserLogin
from zaban.security import WEB_COOKIE_NAMES, read_web_session, session_is_current
from zaban.services.web_sessions import start_web_session
from zaban.services.learner import get_accent, set_accent, set_learner_profile
from zaban.services.placement import level_for_score, public_questions, score_answers
from zaban.services.programs import advance_if_done, ensure_progress
from zaban.services.otp import check_code, development_code, normalize_phone, request_code
from zaban.services.passwords import hash_password, verify_password
from zaban.services.payments import has_active_plan, require_plan

# Sign-in endpoints for the website. They set an HttpOnly cookie, so the browser never holds an API key.
# Adults sign in with a mobile number and a password. Forgotten passwords are reset with an SMS code.
router = APIRouter(prefix="/web")

WRONG_LOGIN = "Wrong phone number or password"
MAX_PASSWORD_FAILURES = 5
PASSWORD_LOCK_MINUTES = 15
Role = Literal["student", "parent"]


def _set_session_cookie(response: Response, role: str, token: str) -> None:
    response.set_cookie(
        WEB_COOKIE_NAMES[role],
        token,
        max_age=settings.web_session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        path="/",
    )


def _guardian_from_cookie(db: DBSession, token: str | None) -> Guardian:
    payload = read_web_session(token) if token else None
    guardian = db.get(Guardian, payload["sid"]) if payload and payload["role"] == "guardian" else None
    if not session_is_current(payload or {}, guardian, db):
        raise HTTPException(status_code=401, detail="Please sign in")
    return guardian


def _self_profile(db: DBSession, guardian: Guardian) -> Student | None:
    return db.query(Student).filter(Student.self_owner_id == guardian.id).first()


def _adult_out(guardian: Guardian) -> dict:
    return {"role": "parent", "name": guardian.full_name}


def _set_adult_cookie(response: Response, guardian: Guardian, db: DBSession, request: Request) -> None:
    token = start_web_session(db, request, "guardian", guardian.id, guardian.tenant_id, guardian.session_version)
    _set_session_cookie(response, "parent", token)


@router.post("/user/otp/request")
def request_otp(body: OtpRequest, request: Request, db: DBSession = Depends(get_db)) -> dict:
    phone = normalize_phone(body.phone)
    if phone is None:
        raise HTTPException(status_code=400, detail="Enter a valid mobile number")
    exists = db.query(Guardian).filter(Guardian.phone == phone).first() is not None
    if body.purpose == "signup" and exists:
        raise HTTPException(status_code=409, detail="This number is already registered. Sign in instead")
    if body.purpose == "reset" and not exists:
        # Same answer as a real reset, so the form does not reveal which numbers have accounts.
        return {"ok": True, "resend_in_seconds": 60}
    ip = request.client.host if request.client else None
    code = request_code(db, phone, ip)
    return {"ok": True, "resend_in_seconds": 60, "dev_code": development_code(code, db)}


@router.post("/user/signup", status_code=201)
def sign_up(body: SignUpCreate, response: Response, request: Request, db: DBSession = Depends(get_db)) -> dict:
    # Open sign-up: anyone who can receive an SMS on this number can create the adult account. No approval step.
    phone = normalize_phone(body.phone)
    if phone is None:
        raise HTTPException(status_code=400, detail="Enter a valid mobile number")
    if not body.age_confirmed:
        raise HTTPException(status_code=400, detail="Only adults can create an account here")
    if db.query(Guardian).filter(Guardian.phone == phone).first():
        raise HTTPException(status_code=409, detail="This number is already registered. Sign in instead")
    tenant = db.query(Tenant).filter(Tenant.status == "active").order_by(Tenant.created_at).first()
    if tenant is None:
        raise HTTPException(status_code=503, detail="The service is not ready yet")

    check_code(db, phone, body.code)
    guardian = Guardian(
        tenant_id=tenant.id,
        phone=phone,
        full_name=body.full_name.strip()[:120],
        password_hash=hash_password(body.password),
        goal=body.goal.strip()[:60] if body.goal else None,
    )
    db.add(guardian)
    db.commit()
    db.refresh(guardian)
    _set_adult_cookie(response, guardian, db, request)
    return _adult_out(guardian)


@router.post("/user/login")
def adult_login(body: UserLogin, response: Response, request: Request, db: DBSession = Depends(get_db)) -> dict:
    phone = normalize_phone(body.phone)
    guardian = db.query(Guardian).filter(Guardian.phone == phone).first() if phone else None
    if guardian is None or guardian.password_hash is None:
        raise HTTPException(status_code=401, detail=WRONG_LOGIN)

    now = utcnow()
    if guardian.suspended:
        raise HTTPException(status_code=403, detail="This account is suspended")
    if guardian.locked_until and guardian.locked_until > now:
        raise HTTPException(status_code=429, detail="Too many wrong passwords. Try again in 15 minutes")
    if not verify_password(body.password, guardian.password_hash):
        guardian.failed_logins += 1
        if guardian.failed_logins >= MAX_PASSWORD_FAILURES:
            guardian.failed_logins = 0
            guardian.locked_until = now + timedelta(minutes=PASSWORD_LOCK_MINUTES)
        db.commit()
        raise HTTPException(status_code=401, detail=WRONG_LOGIN)

    guardian.failed_logins = 0
    guardian.locked_until = None
    # One sign-in per account: a new sign-in ends the older ones on other devices, the adult's and their own learning.
    guardian.session_version += 1
    self_profile = _self_profile(db, guardian)
    if self_profile:
        self_profile.session_version += 1
    # Every recorded sign-in of this adult and of their learner profile ends too.
    subject_ids = [guardian.id] + ([self_profile.id] if self_profile else [])
    db.query(WebSession).filter(WebSession.subject_id.in_(subject_ids), WebSession.revoked_at.is_(None)).update(
        {"revoked_at": utcnow()}, synchronize_session=False
    )
    db.commit()
    _set_adult_cookie(response, guardian, db, request)
    return _adult_out(guardian)


@router.post("/user/password/reset")
def reset_password(body: PasswordReset, db: DBSession = Depends(get_db)) -> dict:
    phone = normalize_phone(body.phone)
    guardian = db.query(Guardian).filter(Guardian.phone == phone).first() if phone else None
    if guardian is None:
        raise HTTPException(status_code=401, detail="Invalid or expired code. Request a new one")
    check_code(db, phone, body.code)
    guardian.password_hash = hash_password(body.password)
    # A new password ends every older sign-in for this adult, and clears any lock.
    guardian.session_version += 1
    guardian.failed_logins = 0
    guardian.locked_until = None
    db.commit()
    return {"ok": True}


@router.post("/user/self")
def start_own_learning(
    response: Response,
    request: Request,
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    # An adult who wants to learn for themself gets one learner profile. Only that adult can see its reports.
    guardian = _guardian_from_cookie(db, zaban_parent)
    require_plan(guardian)
    student = _self_profile(db, guardian)
    if student is None:
        student = Student(
            tenant_id=guardian.tenant_id,
            external_user_id=f"self-{guardian.id}",
            display_name=guardian.full_name,
            self_owner_id=guardian.id,
            age_band="adult",
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        # The adult agrees to their own lessons when the profile is created, so no parent consent is needed.
        db.add(Consent(student_id=student.id, text_version="self-v1"))
        # The goal the adult chose at sign-up becomes the learner's motivation for lessons.
        set_learner_profile(db, student.id, motivation=guardian.goal or "")
        db.commit()

    token = start_web_session(db, request, "student", student.id, student.tenant_id, student.session_version)
    _set_session_cookie(response, "student", token)
    return {"role": "student", "name": student.display_name, "id": student.id}


@router.post("/user/logout-all")
def logout_everywhere(
    response: Response,
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    # Invalidates every sign-in for this adult and for their own learner profile.
    guardian = _guardian_from_cookie(db, zaban_parent)
    guardian.session_version += 1
    self_profile = _self_profile(db, guardian)
    if self_profile:
        self_profile.session_version += 1
    # Every recorded sign-in of this adult and of their learner profile ends too.
    subject_ids = [guardian.id] + ([self_profile.id] if self_profile else [])
    db.query(WebSession).filter(WebSession.subject_id.in_(subject_ids), WebSession.revoked_at.is_(None)).update(
        {"revoked_at": utcnow()}, synchronize_session=False
    )
    db.commit()
    response.delete_cookie(WEB_COOKIE_NAMES["parent"], path="/")
    response.delete_cookie(WEB_COOKIE_NAMES["student"], path="/")
    return {"ok": True}


@router.post("/logout")
def logout(
    response: Response,
    role: Role = "student",
    zaban_parent: str | None = Cookie(default=None),
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    # Ends this device's sign-in, so the same cookie cannot be used again.
    token = zaban_parent if role == "parent" else zaban_student
    payload = read_web_session(token) if token else None
    row = db.get(WebSession, payload.get("j") or "") if payload else None
    if row is not None and row.revoked_at is None:
        row.revoked_at = utcnow()
        db.commit()
    response.delete_cookie(WEB_COOKIE_NAMES[role], path="/")
    return {"ok": True}


def _student_from_cookie(db: DBSession, token: str | None) -> Student:
    payload = read_web_session(token) if token else None
    student = db.get(Student, payload["sid"]) if payload and payload["role"] == "student" else None
    if not session_is_current(payload or {}, student, db):
        raise HTTPException(status_code=401, detail="Please sign in")
    return student


@router.get("/student/voice-samples")
def list_voice_samples(zaban_student: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> list[dict]:
    _student_from_cookie(db, zaban_student)
    rows = db.query(VoiceSample).order_by(VoiceSample.created_at.desc()).all()
    return [{"id": s.id, "name": s.name, "accent": s.accent} for s in rows]


@router.get("/student/voice-samples/{sample_id}/audio")
def voice_sample_audio(
    sample_id: str,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> Response:
    _student_from_cookie(db, zaban_student)
    sample = db.get(VoiceSample, sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(content=sample.data, media_type=sample.mime, headers={"Cache-Control": "private, max-age=3600"})


@router.get("/student/accent")
def read_accent(zaban_student: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> dict:
    student = _student_from_cookie(db, zaban_student)
    return {"accent": get_accent(db, student.id)}


@router.post("/student/accent")
def choose_accent(
    body: AccentChoice,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    student = _student_from_cookie(db, zaban_student)
    set_accent(db, student.id, body.accent)
    db.commit()
    return {"accent": body.accent}


# The learner's own short level check. It works only while the level is not set yet.
@router.get("/student/level-test")
def level_test_questions(zaban_student: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> list[dict]:
    _student_from_cookie(db, zaban_student)
    return public_questions()


@router.post("/student/level-test")
def submit_level_test(
    body: LevelTestAnswers,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    student = _student_from_cookie(db, zaban_student)
    if student.cefr_level:
        raise HTTPException(status_code=409, detail="Level is already set")
    score = score_answers(body.answers)
    student.cefr_level = level_for_score(score)
    db.commit()
    return {"score": score, "total": len(body.answers), "level": student.cefr_level}


@router.get("/me")
def me(
    role: Role = "student",
    zaban_student: str | None = Cookie(default=None),
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    token = zaban_student if role == "student" else zaban_parent
    payload = read_web_session(token) if token else None
    if payload is None:
        raise HTTPException(status_code=401, detail="Please sign in")
    if payload["role"] == "student":
        student = db.get(Student, payload["sid"])
        if session_is_current(payload, student, db):
            # Lessons need the plan of the adult who owns this learner profile.
            owner_id = student.guardian_id or student.self_owner_id
            owner = db.get(Guardian, owner_id) if owner_id else None
            return {
                "role": "student",
                "name": student.display_name or student.username,
                "id": student.id,
                "has_active_plan": True if owner is None else has_active_plan(owner),
            }
    if payload["role"] == "guardian":
        guardian = db.get(Guardian, payload["sid"])
        if session_is_current(payload, guardian, db):
            return {
                "role": "parent",
                "name": guardian.full_name,
                "has_own_learning": _self_profile(db, guardian) is not None,
                "has_active_plan": has_active_plan(guardian),
            }
    raise HTTPException(status_code=401, detail="Please sign in")


@router.get("/student/program")
def student_program(zaban_student: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> dict:
    # The learner's place in their program: where they are, the lesson they are on, and the whole list with its state.
    student = _student_from_cookie(db, zaban_student)
    progress = ensure_progress(db, student)
    if progress is None:
        db.commit()
        return {"program": None}
    advance_if_done(db, student.id)
    db.commit()
    program = db.get(LearningProgram, progress.program_id)
    items = db.query(ProgramItem).filter(ProgramItem.program_id == program.id).order_by(ProgramItem.position).all()
    current = next((i for i in items if i.position == progress.position), None)
    return {
        "program": {
            "name": program.name,
            "goal": program.goal,
            "total": len(items),
            "done": min(progress.position, len(items)),
            "status": progress.status,
            "block_size": program.block_size,
        },
        "current": (
            {"number": current.position + 1, "title": current.title, "title_en": current.title_en, "activity": current.activity, "phrases": current.phrases}
            if current is not None and progress.status == "active"
            else None
        ),
        "items": [
            {
                "number": i.position + 1,
                "title": i.title,
                "title_en": i.title_en,
                "state": "done" if i.position < progress.position else ("current" if i.position == progress.position else "next"),
            }
            for i in items
        ],
    }
