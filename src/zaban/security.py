import hashlib
import secrets
from dataclasses import dataclass

from fastapi import Cookie, Depends, Header, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from zaban.config import settings
from zaban.db import get_db
from zaban.models import Guardian, Student, Tenant, utcnow

# One cookie per role, so a parent and a child can be signed in on the same computer at the same time.
WEB_COOKIE_NAMES = {"student": "zaban_student", "parent": "zaban_parent"}

_token_serializer = URLSafeTimedSerializer(settings.secret_key, salt="student-token")
_web_serializer = URLSafeTimedSerializer(settings.secret_key, salt="web-session")


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> str:
    return "zb_live_" + secrets.token_urlsafe(24)


def issue_student_token(student: Student) -> str:
    return _token_serializer.dumps({"sid": student.id, "tid": student.tenant_id})


def issue_web_session(role: str, subject_id: str, tenant_id: str) -> str:
    return _web_serializer.dumps({"role": role, "sid": subject_id, "tid": tenant_id})


def read_web_session(token: str) -> dict | None:
    try:
        return _web_serializer.loads(token, max_age=settings.web_session_ttl_seconds)
    except (BadSignature, SignatureExpired):
        return None


def _read_student_token(token: str) -> dict:
    try:
        return _token_serializer.loads(token, max_age=settings.session_token_ttl_seconds)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _check_tenant(tenant: Tenant | None) -> Tenant:
    if tenant is None or tenant.status != "active":
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if tenant.expires_at and tenant.expires_at < utcnow():
        raise HTTPException(status_code=403, detail="Subscription expired")
    return tenant


@dataclass(frozen=True)
class Auth:
    tenant: Tenant
    # Exactly one of these is set for student and parent callers. Tenant API keys leave both as None.
    student_id: str | None = None
    guardian_id: str | None = None


def get_auth(
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    zaban_student: str | None = Cookie(default=None),
    zaban_parent: str | None = Cookie(default=None),
    x_zaban_role: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Auth:
    if x_api_key:
        tenant = db.query(Tenant).filter(Tenant.api_key_hash == hash_api_key(x_api_key)).first()
        return Auth(tenant=_check_tenant(tenant))

    if authorization and authorization.startswith("Bearer "):
        payload = _read_student_token(authorization.removeprefix("Bearer ").strip())
        tenant = _check_tenant(db.get(Tenant, payload["tid"]))
        return Auth(tenant=tenant, student_id=payload["sid"])

    # The page says which role it is acting as, so a shared computer never mixes the two sessions up.
    cookies = (zaban_parent, zaban_student) if x_zaban_role == "parent" else (zaban_student, zaban_parent)
    for token in cookies:
        payload = read_web_session(token) if token else None
        if not payload:
            continue
        tenant = _check_tenant(db.get(Tenant, payload["tid"]))
        if payload["role"] == "student" and db.get(Student, payload["sid"]):
            return Auth(tenant=tenant, student_id=payload["sid"])
        if payload["role"] == "guardian" and db.get(Guardian, payload["sid"]):
            return Auth(tenant=tenant, guardian_id=payload["sid"])

    raise HTTPException(status_code=401, detail="Please sign in")


def require_tenant(auth: Auth = Depends(get_auth)) -> Tenant:
    if auth.student_id or auth.guardian_id:
        raise HTTPException(status_code=403, detail="Tenant API key required")
    return auth.tenant


def require_manager(auth: Auth = Depends(get_auth)) -> Auth:
    # Tenant API keys and parents can manage students. Students cannot.
    if auth.student_id:
        raise HTTPException(status_code=403, detail="Not allowed for students")
    return auth


def get_student_for_auth(db: Session, auth: Auth, student_id: str) -> Student:
    student = db.get(Student, student_id)
    if student is None or student.tenant_id != auth.tenant.id:
        raise HTTPException(status_code=404, detail="Student not found")
    if auth.student_id is not None and auth.student_id != student.id:
        raise HTTPException(status_code=403, detail="Not allowed for this student")
    if auth.guardian_id is not None and student.guardian_id != auth.guardian_id:
        raise HTTPException(status_code=404, detail="Student not found")
    return student
