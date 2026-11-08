from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from zaban.config import settings
from zaban.db import get_db
from zaban.models import BillingPlan, Payment, utcnow
from zaban.services.payments import confirm_payment, get_gateway, has_active_plan, mark_paid
from zaban.services.settings_store import PAYMENT_PROVIDER_KEY, get_setting
from zaban.web import _guardian_from_cookie

# Plans, checkout and payment status for adult accounts. The browser never decides that a payment succeeded.
router = APIRouter(prefix="/web/billing")


class CheckoutCreate(BaseModel):
    plan_id: str = Field(min_length=1, max_length=32)


class FakeConfirm(BaseModel):
    payment_id: str = Field(min_length=1, max_length=32)
    ok: bool


def _plan_out(plan: BillingPlan) -> dict:
    return {
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "price_toman": plan.price_toman,
        "days": plan.days,
    }


def _payment_out(payment: Payment, plan: BillingPlan | None) -> dict:
    return {
        "id": payment.id,
        "plan_name": plan.name if plan else "",
        "amount_toman": payment.amount_toman,
        "status": payment.status,
        "created_at": payment.created_at.isoformat(),
        "confirmed_at": payment.confirmed_at.isoformat() if payment.confirmed_at else None,
    }


@router.get("/plans")
def list_plans(db: DBSession = Depends(get_db)) -> list[dict]:
    plans = db.query(BillingPlan).filter(BillingPlan.active.is_(True)).order_by(BillingPlan.price_toman).all()
    return [_plan_out(p) for p in plans]


@router.get("/status")
def billing_status(zaban_parent: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> dict:
    guardian = _guardian_from_cookie(db, zaban_parent)
    payments = (
        db.query(Payment)
        .filter(Payment.guardian_id == guardian.id)
        .order_by(Payment.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "has_active_plan": has_active_plan(guardian),
        "plan_expires_at": guardian.plan_expires_at.isoformat() if guardian.plan_expires_at else None,
        "payments": [_payment_out(p, db.get(BillingPlan, p.plan_id)) for p in payments],
    }


@router.post("/checkout", status_code=201)
def checkout(
    body: CheckoutCreate,
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    guardian = _guardian_from_cookie(db, zaban_parent)
    plan = db.get(BillingPlan, body.plan_id)
    if plan is None or not plan.active:
        raise HTTPException(status_code=404, detail="This plan is not available")

    gateway = get_gateway(get_setting(db, PAYMENT_PROVIDER_KEY, settings.payment_gateway))
    payment = Payment(
        guardian_id=guardian.id,
        plan_id=plan.id,
        amount_toman=plan.price_toman,
        gateway=gateway.name,
        created_at=utcnow(),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    try:
        redirect = gateway.start(payment)
    except HTTPException:
        payment.status = "failed"
        db.commit()
        raise
    db.commit()
    return {"payment_id": payment.id, "redirect": redirect}


@router.get("/zarinpal/callback")
def zarinpal_callback(
    payment_id: str,
    Authority: str = "",
    Status: str = "",
    db: DBSession = Depends(get_db),
) -> Response:
    # The buyer comes back here from ZarinPal. The payment is marked paid only after ZarinPal verifies it.
    payment = db.get(Payment, payment_id)
    if payment is None or payment.gateway != "zarinpal" or payment.gateway_ref != Authority or Status != "OK":
        return RedirectResponse(url="/parent?payment=failed", status_code=303)
    if get_gateway("zarinpal").verify(payment, Authority):
        mark_paid(db, payment)
        return RedirectResponse(url="/parent?payment=paid", status_code=303)
    payment.status = "failed"
    db.commit()
    return RedirectResponse(url="/parent?payment=failed", status_code=303)


@router.post("/fake/confirm")
def fake_confirm(
    body: FakeConfirm,
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    # Development only. It stands in for the gateway's callback, so the flow can be tested without a merchant account.
    if settings.environment == "production":
        raise HTTPException(status_code=404, detail="Not found")
    guardian = _guardian_from_cookie(db, zaban_parent)
    payment = db.get(Payment, body.payment_id)
    if payment is None or payment.guardian_id != guardian.id or payment.gateway != "fake":
        raise HTTPException(status_code=404, detail="Payment not found")
    if body.ok:
        mark_paid(db, payment)
    else:
        confirm_payment(db, payment, False)
    return {"status": payment.status}
