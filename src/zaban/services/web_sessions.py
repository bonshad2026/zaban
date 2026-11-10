from fastapi import Request
from sqlalchemy.orm import Session as DBSession

from zaban.models import WebSession
from zaban.security import issue_web_session


def start_web_session(db: DBSession, request: Request, role: str, subject_id: str, tenant_id: str, version: int) -> str:
    # Records one sign-in with its device and address, and returns the cookie value for it.
    row = WebSession(
        tenant_id=tenant_id,
        role=role,
        subject_id=subject_id,
        user_agent=(request.headers.get("user-agent") or "")[:200],
        ip=(request.client.host if request.client else "")[:64],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return issue_web_session(role, subject_id, tenant_id, version, row.id)
