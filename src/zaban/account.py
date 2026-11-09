from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from zaban.db import get_db
from zaban.models import ConsultRequest, CooperationRequest, Guardian, Student
from zaban.security import read_web_session, session_is_current
from zaban.services.otp import normalize_phone
from zaban.services.passwords import hash_password, verify_password

# Account pages for the website: the adult's profile, and the requests the adult has sent.
# A learner who is signed in sees the account of the adult who owns the learner profile.
router = APIRouter(prefix="/web/user")

WRONG_PASSWORD = "The current password is not correct"

STATUS_FA = {
    "new": "ثبت شد",
    "reviewed": "بررسی شد",
    "called": "تماس گرفته شد",
    "recall": "تماس دوباره",
    "awaiting_reply": "منتظر پاسخ",
    "contacted": "تماس گرفته شد",
    "closed": "بسته شد",
}


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


def _adult_from_cookies(db: DBSession, parent_token: str | None, student_token: str | None) -> Guardian:
    payload = read_web_session(parent_token) if parent_token else None
    if payload and payload["role"] == "guardian":
        guardian = db.get(Guardian, payload["sid"])
        if session_is_current(payload, guardian):
            return guardian
    payload = read_web_session(student_token) if student_token else None
    if payload and payload["role"] == "student":
        student = db.get(Student, payload["sid"])
        if session_is_current(payload, student):
            owner_id = student.guardian_id or student.self_owner_id
            owner = db.get(Guardian, owner_id) if owner_id else None
            if owner is not None:
                return owner
    raise HTTPException(status_code=401, detail="Please sign in")


@router.get("/profile")
def read_profile(
    zaban_parent: str | None = Cookie(default=None),
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    adult = _adult_from_cookies(db, zaban_parent, zaban_student)
    return {"name": adult.full_name, "phone": adult.phone, "goal": adult.goal}


@router.put("/profile")
def update_profile(
    body: ProfileUpdate,
    zaban_parent: str | None = Cookie(default=None),
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    adult = _adult_from_cookies(db, zaban_parent, zaban_student)
    adult.full_name = body.full_name.strip()[:120]
    db.commit()
    return {"name": adult.full_name, "phone": adult.phone, "goal": adult.goal}


@router.post("/password")
def change_password(
    body: PasswordChange,
    zaban_parent: str | None = Cookie(default=None),
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    adult = _adult_from_cookies(db, zaban_parent, zaban_student)
    if adult.password_hash is None or not verify_password(body.current_password, adult.password_hash):
        raise HTTPException(status_code=400, detail=WRONG_PASSWORD)
    adult.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}


@router.get("/requests")
def my_requests(
    zaban_parent: str | None = Cookie(default=None),
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    adult = _adult_from_cookies(db, zaban_parent, zaban_student)
    consult = [
        {
            "id": row.id,
            "kind": "consult",
            "subject": row.subject or "مشاوره",
            "status": STATUS_FA.get(row.status, row.status),
            "created_at": row.created_at.isoformat(),
        }
        for row in db.query(ConsultRequest).order_by(ConsultRequest.created_at.desc()).all()
        if normalize_phone(row.phone) == adult.phone
    ]
    cooperation = [
        {
            "id": row.id,
            "kind": "cooperation",
            "subject": row.subject,
            "status": STATUS_FA.get(row.status, row.status),
            "created_at": row.created_at.isoformat(),
        }
        for row in db.query(CooperationRequest).order_by(CooperationRequest.created_at.desc()).all()
        if normalize_phone(row.phone) == adult.phone
    ]
    return {"consult": consult, "cooperation": cooperation}
