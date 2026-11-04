import hmac
from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from zaban.config import settings
from zaban.db import get_db
from zaban.models import BillingPlan, ConsultRequest, Guardian, Payment, utcnow
from zaban.services.payments import confirm_payment

# Operator page. One shared password from the environment (ADMIN_PASSWORD). Sessions last 12 hours.
router = APIRouter(prefix="/admin/api")

ADMIN_COOKIE = "zaban_admin"
ADMIN_TTL_SECONDS = 12 * 60 * 60
_admin_serializer = URLSafeTimedSerializer(settings.secret_key, salt="admin-session")


def require_admin(token: str | None = Cookie(default=None, alias=ADMIN_COOKIE)) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Please sign in")
    try:
        _admin_serializer.loads(token, max_age=ADMIN_TTL_SECONDS)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Please sign in")


class AdminLogin(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class StatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(new|contacted|closed)$")


class PaymentDecision(BaseModel):
    ok: bool


class PlanGrant(BaseModel):
    days: int = Field(ge=1, le=3650)


class PlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=300)
    price_toman: int = Field(ge=0)
    days: int = Field(ge=1, le=3650)


class PlanUpdate(BaseModel):
    active: bool


@router.post("/login")
def admin_login(body: AdminLogin, response: Response) -> dict:
    if not settings.admin_password:
        raise HTTPException(status_code=503, detail="The admin page is not configured")
    if not hmac.compare_digest(body.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="Wrong password")
    token = _admin_serializer.dumps({"adm": True})
    response.set_cookie(
        ADMIN_COOKIE,
        token,
        max_age=ADMIN_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        secure=settings.environment == "production",
        path="/",
    )
    return {"ok": True}


@router.post("/logout")
def admin_logout(response: Response) -> dict:
    response.delete_cookie(ADMIN_COOKIE, path="/")
    return {"ok": True}


@router.get("/consults", dependencies=[Depends(require_admin)])
def list_consults(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(ConsultRequest).order_by(ConsultRequest.created_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "phone": r.phone,
            "message": r.message,
            "preferred_time": r.preferred_time,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/consults/{consult_id}/status", dependencies=[Depends(require_admin)])
def update_consult(consult_id: int, body: StatusUpdate, db: DBSession = Depends(get_db)) -> dict:
    item = db.get(ConsultRequest, consult_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    item.status = body.status
    db.commit()
    return {"ok": True}


@router.get("/adults", dependencies=[Depends(require_admin)])
def list_adults(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(Guardian).order_by(Guardian.created_at.desc()).limit(300).all()
    return [
        {
            "id": g.id,
            "name": g.full_name,
            "phone": g.phone,
            "goal": g.goal,
            "plan_expires_at": g.plan_expires_at.isoformat() if g.plan_expires_at else None,
            "created_at": g.created_at.isoformat(),
        }
        for g in rows
    ]


@router.post("/adults/{adult_id}/grant", dependencies=[Depends(require_admin)])
def grant_days(adult_id: str, body: PlanGrant, db: DBSession = Depends(get_db)) -> dict:
    # Manual extension, for example for a support case. The same rule as a paid plan applies.
    guardian = db.get(Guardian, adult_id)
    if guardian is None:
        raise HTTPException(status_code=404, detail="Not found")
    now = utcnow()
    start = max(now, guardian.plan_expires_at) if guardian.plan_expires_at else now
    guardian.plan_expires_at = start + timedelta(days=body.days)
    db.commit()
    return {"plan_expires_at": guardian.plan_expires_at.isoformat()}


@router.get("/payments", dependencies=[Depends(require_admin)])
def list_payments(status: str = "pending", db: DBSession = Depends(get_db)) -> list[dict]:
    query = db.query(Payment).order_by(Payment.created_at.desc())
    if status != "all":
        query = query.filter(Payment.status == status)
    out = []
    for p in query.limit(200).all():
        guardian = db.get(Guardian, p.guardian_id)
        plan = db.get(BillingPlan, p.plan_id)
        out.append(
            {
                "id": p.id,
                "adult": guardian.full_name if guardian else "",
                "phone": guardian.phone if guardian else "",
                "plan": plan.name if plan else "",
                "amount_toman": p.amount_toman,
                "status": p.status,
                "gateway": p.gateway,
                "created_at": p.created_at.isoformat(),
            }
        )
    return out


@router.post("/payments/{payment_id}/decision", dependencies=[Depends(require_admin)])
def decide_payment(payment_id: str, body: PaymentDecision, db: DBSession = Depends(get_db)) -> dict:
    # For payments the gateway could not report back. Confirming here follows the same rule as a gateway callback.
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Not found")
    confirm_payment(db, payment, body.ok)
    return {"status": payment.status}


@router.get("/plans", dependencies=[Depends(require_admin)])
def list_plans(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(BillingPlan).order_by(BillingPlan.price_toman).all()
    return [
        {"id": p.id, "name": p.name, "description": p.description, "price_toman": p.price_toman, "days": p.days, "active": p.active}
        for p in rows
    ]


@router.post("/plans", status_code=201, dependencies=[Depends(require_admin)])
def create_plan(body: PlanCreate, db: DBSession = Depends(get_db)) -> dict:
    plan = BillingPlan(name=body.name.strip(), description=body.description.strip(), price_toman=body.price_toman, days=body.days)
    db.add(plan)
    db.commit()
    return {"id": plan.id}


@router.post("/plans/{plan_id}/active", dependencies=[Depends(require_admin)])
def set_plan_active(plan_id: str, body: PlanUpdate, db: DBSession = Depends(get_db)) -> dict:
    plan = db.get(BillingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Not found")
    plan.active = body.active
    db.commit()
    return {"ok": True}
