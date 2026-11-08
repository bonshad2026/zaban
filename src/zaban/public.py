from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from zaban.db import get_db
from zaban.models import ConsultRequest, CooperationRequest, utcnow
from zaban.schemas import CooperationCreate
from zaban.services.otp import normalize_phone

# Public forms. Nobody needs to sign in to send a consultation request.
router = APIRouter(prefix="/public")

MAX_CONSULT_PER_IP_PER_HOUR = 10


class ConsultCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    last_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=24)
    subject: str = Field(min_length=2, max_length=160)
    message: str = Field(default="", max_length=1000)
    preferred_time: str | None = Field(default=None, max_length=60)
    # The caller must agree to be phoned back. The request is refused without it.
    contact_permission: Literal[True]


@router.post("/consult", status_code=201)
def create_consult_request(body: ConsultCreate, request: Request, db: DBSession = Depends(get_db)) -> dict:
    phone = normalize_phone(body.phone)
    if phone is None:
        raise HTTPException(status_code=400, detail="Enter a valid mobile number")
    ip = request.client.host if request.client else None
    if ip:
        recent = (
            db.query(ConsultRequest)
            .filter(ConsultRequest.request_ip == ip, ConsultRequest.created_at >= utcnow() - timedelta(hours=1))
            .count()
        )
        if recent >= MAX_CONSULT_PER_IP_PER_HOUR:
            raise HTTPException(status_code=429, detail="Too many requests. Try again later")

    item = ConsultRequest(
        name=body.name.strip(),
        last_name=body.last_name.strip(),
        subject=body.subject.strip(),
        contact_permission=body.contact_permission,
        phone=phone,
        message=body.message.strip(),
        preferred_time=(body.preferred_time or "").strip() or None,
        request_ip=ip,
    )
    db.add(item)
    db.commit()
    return {"ok": True, "message": "Your request was received. We will call you."}


@router.post("/cooperation", status_code=201)
def create_cooperation_request(body: CooperationCreate, request: Request, db: DBSession = Depends(get_db)) -> dict:
    phone = normalize_phone(body.phone)
    if phone is None:
        raise HTTPException(status_code=400, detail="Enter a valid mobile number")
    ip = request.client.host if request.client else None
    if ip:
        recent = (
            db.query(CooperationRequest)
            .filter(CooperationRequest.request_ip == ip, CooperationRequest.created_at >= utcnow() - timedelta(hours=1))
            .count()
        )
        if recent >= MAX_CONSULT_PER_IP_PER_HOUR:
            raise HTTPException(status_code=429, detail="Too many requests. Try again later")

    item = CooperationRequest(
        subject=body.subject.strip(),
        phone=phone,
        email=(body.email or "").strip() or None,
        message=body.message.strip(),
        request_ip=ip,
    )
    db.add(item)
    db.commit()
    return {"ok": True, "message": "Your request was received. We will contact you."}
