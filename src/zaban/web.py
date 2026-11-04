from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session as DBSession

from zaban.config import settings
from zaban.db import get_db
from zaban.models import Consent, Guardian, Student, Tenant, utcnow
from zaban.schemas import OtpRequest, OtpVerify, StudentLogin
from zaban.security import WEB_COOKIE_NAMES, issue_web_session, read_web_session, session_is_current
from zaban.services.otp import check_code, normalize_phone, request_code
from zaban.services.passwords import verify_password

# Sign-in endpoints for the website. They set an HttpOnly cookie, so the browser never holds an API key.
# Adults sign in with a mobile number and an SMS code. Children sign in with a username and PIN.
router = APIRouter(prefix="/web")

WRONG_PIN = "Wrong username or PIN"
MAX_PIN_FAILURES = 3
PIN_LOCK_MINUTES = 15
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
    if not session_is_current(payload or {}, guardian):
        raise HTTPException(status_code=401, detail="Please sign in")
    return guardian


def _self_profile(db: DBSession, guardian: Guardian) -> Student | None:
    return db.query(Student).filter(Student.self_owner_id == guardian.id).first()


@router.post("/user/otp/request")
def request_otp(body: OtpRequest, request: Request, db: DBSession = Depends(get_db)) -> dict:
    phone = normalize_phone(body.phone)
    if phone is None:
        raise HTTPException(status_code=400, detail="Enter a valid mobile number")
    ip = request.client.host if request.client else None
    request_code(db, phone, ip)
    return {"ok": True, "resend_in_seconds": 60}


@router.post("/user/otp/verify")
def verify_otp(body: OtpVerify, response: Response, db: DBSession = Depends(get_db)) -> dict:
    phone = normalize_phone(body.phone)
    if phone is None:
        raise HTTPException(status_code=400, detail="Enter a valid mobile number")

    guardian = db.query(Guardian).filter(Guardian.phone == phone).first()
    name = (body.full_name or "").strip()
    if guardian is None and not name:
        # Checked before the code is used, so a first-time visitor who forgot the name can retry with the same code.
        raise HTTPException(status_code=400, detail="Your name is needed to create an account")

    check_code(db, phone, body.code)

    if guardian is None:
        tenant = db.query(Tenant).filter(Tenant.status == "active").order_by(Tenant.created_at).first()
        if tenant is None:
            raise HTTPException(status_code=503, detail="The service is not ready yet")
        guardian = Guardian(tenant_id=tenant.id, phone=phone, full_name=name[:120])
        db.add(guardian)
        db.commit()
        db.refresh(guardian)

    _set_session_cookie(response, "parent", issue_web_session("guardian", guardian.id, guardian.tenant_id, guardian.session_version))
    return {"role": "parent", "name": guardian.full_name}


@router.post("/student/login")
def student_login(body: StudentLogin, response: Response, db: DBSession = Depends(get_db)) -> dict:
    student = db.query(Student).filter(Student.username == body.username.strip().lower()).first()
    if student is None:
        raise HTTPException(status_code=401, detail=WRONG_PIN)

    now = utcnow()
    if student.locked_until and student.locked_until > now:
        raise HTTPException(status_code=429, detail="Too many wrong PINs. Try again in 15 minutes")

    if student.password_hash is None or not verify_password(body.password, student.password_hash):
        student.failed_logins += 1
        if student.failed_logins >= MAX_PIN_FAILURES:
            student.failed_logins = 0
            student.locked_until = now + timedelta(minutes=PIN_LOCK_MINUTES)
        db.commit()
        raise HTTPException(status_code=401, detail=WRONG_PIN)

    student.failed_logins = 0
    student.locked_until = None
    db.commit()
    _set_session_cookie(
        response, "student", issue_web_session("student", student.id, student.tenant_id, student.session_version)
    )
    return {"role": "student", "name": student.display_name or student.username}


@router.post("/user/self")
def start_own_learning(
    response: Response,
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    # An adult who wants to learn for themself gets one learner profile. Only that adult can see its reports.
    guardian = _guardian_from_cookie(db, zaban_parent)
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
        db.commit()

    _set_session_cookie(
        response, "student", issue_web_session("student", student.id, student.tenant_id, student.session_version)
    )
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
    db.commit()
    response.delete_cookie(WEB_COOKIE_NAMES["parent"], path="/")
    response.delete_cookie(WEB_COOKIE_NAMES["student"], path="/")
    return {"ok": True}


@router.post("/logout")
def logout(response: Response, role: Role = "student") -> dict:
    response.delete_cookie(WEB_COOKIE_NAMES[role], path="/")
    return {"ok": True}


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
        if session_is_current(payload, student):
            return {"role": "student", "name": student.display_name or student.username, "id": student.id}
    if payload["role"] == "guardian":
        guardian = db.get(Guardian, payload["sid"])
        if session_is_current(payload, guardian):
            return {
                "role": "parent",
                "name": guardian.full_name,
                "has_own_learning": _self_profile(db, guardian) is not None,
            }
    raise HTTPException(status_code=401, detail="Please sign in")
