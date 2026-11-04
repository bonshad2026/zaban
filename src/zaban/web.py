from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session as DBSession

from zaban.config import settings
from zaban.db import get_db
from zaban.models import Guardian, Student
from zaban.schemas import ParentLogin, StudentLogin
from zaban.security import WEB_COOKIE_NAMES, issue_web_session, read_web_session
from zaban.services.passwords import verify_password

# Sign-in endpoints for the website. They set an HttpOnly cookie, so the browser never holds an API key.
router = APIRouter(prefix="/web")

WRONG_LOGIN = "Wrong email or password"
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


@router.post("/student/login")
def student_login(body: StudentLogin, response: Response, db: DBSession = Depends(get_db)) -> dict:
    student = db.query(Student).filter(Student.username == body.username.strip().lower()).first()
    if student is None or student.password_hash is None or not verify_password(body.password, student.password_hash):
        raise HTTPException(status_code=401, detail=WRONG_LOGIN)
    _set_session_cookie(response, "student", issue_web_session("student", student.id, student.tenant_id))
    return {"role": "student", "name": student.display_name or student.username}


@router.post("/parent/login")
def parent_login(body: ParentLogin, response: Response, db: DBSession = Depends(get_db)) -> dict:
    guardian = db.query(Guardian).filter(Guardian.email == body.email.strip().lower()).first()
    if guardian is None or not verify_password(body.password, guardian.password_hash):
        raise HTTPException(status_code=401, detail=WRONG_LOGIN)
    _set_session_cookie(response, "parent", issue_web_session("guardian", guardian.id, guardian.tenant_id))
    return {"role": "parent", "name": guardian.full_name}


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
        if student:
            return {"role": "student", "name": student.display_name or student.username, "id": student.id}
    if payload["role"] == "guardian":
        guardian = db.get(Guardian, payload["sid"])
        if guardian:
            return {"role": "parent", "name": guardian.full_name}
    raise HTTPException(status_code=401, detail="Please sign in")
