import re
from typing import Literal

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
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# The browser sends a square JPEG, PNG or WebP photo of a few kilobytes, so this limit is generous.
AVATAR_PATTERN = re.compile(r"^data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]{1,200000}$")

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
    # Every field is optional. Only the fields that are sent change, so the old profile page still works.
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, max_length=190)
    age: int | None = Field(default=None, ge=18, le=120)
    gender: Literal["female", "male"] | None = None
    avatar: str | None = Field(default=None, max_length=200_000)
    # The learning goal. The same choices the sign-up form used to offer. None clears it.
    goal: Literal["مکالمه‌ی روزمره", "سفر", "کار و شغل", "آزمون", "مدرسه"] | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


def _adult_from_cookies(db: DBSession, parent_token: str | None, student_token: str | None) -> Guardian:
    payload = read_web_session(parent_token) if parent_token else None
    if payload and payload["role"] == "guardian":
        guardian = db.get(Guardian, payload["sid"])
        if session_is_current(payload, guardian, db):
            return guardian
    payload = read_web_session(student_token) if student_token else None
    if payload and payload["role"] == "student":
        student = db.get(Student, payload["sid"])
        if session_is_current(payload, student, db):
            owner_id = student.guardian_id or student.self_owner_id
            owner = db.get(Guardian, owner_id) if owner_id else None
            if owner is not None:
                return owner
    raise HTTPException(status_code=401, detail="Please sign in")


def _profile_out(adult: Guardian) -> dict:
    # The phone number is the sign-in, so it is shown but cannot be changed here.
    return {
        "name": adult.full_name,
        "phone": adult.phone,
        "email": adult.email or "",
        "age": adult.age,
        "gender": adult.gender or "",
        "goal": adult.goal,
        "avatar": adult.avatar_data or "",
    }


@router.get("/profile")
def read_profile(
    zaban_parent: str | None = Cookie(default=None),
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    return _profile_out(_adult_from_cookies(db, zaban_parent, zaban_student))


@router.put("/profile")
def update_profile(
    body: ProfileUpdate,
    zaban_parent: str | None = Cookie(default=None),
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    adult = _adult_from_cookies(db, zaban_parent, zaban_student)
    sent = body.model_fields_set
    if "full_name" in sent:
        if not body.full_name or not body.full_name.strip():
            raise HTTPException(status_code=400, detail="Your name is needed")
        adult.full_name = body.full_name.strip()[:120]
    if "email" in sent:
        email = (body.email or "").strip().lower()
        if email and not EMAIL_PATTERN.match(email):
            raise HTTPException(status_code=400, detail="Enter a valid email address")
        if email and db.query(Guardian).filter(Guardian.email == email, Guardian.id != adult.id).first():
            raise HTTPException(status_code=409, detail="This email is already used by another account")
        adult.email = email or None
    if "age" in sent:
        adult.age = body.age
    if "gender" in sent:
        adult.gender = body.gender
    if "goal" in sent:
        adult.goal = body.goal
    if "avatar" in sent:
        avatar = body.avatar or ""
        if avatar and not AVATAR_PATTERN.match(avatar):
            raise HTTPException(status_code=400, detail="The photo must be a JPG, PNG or WebP image")
        adult.avatar_data = avatar or None
    db.commit()
    return _profile_out(adult)


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
