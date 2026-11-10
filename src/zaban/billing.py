import math

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from zaban.config import settings
from zaban.db import get_db
from zaban.models import BillingPlan, Payment, utcnow
from zaban.services.payments import confirm_payment, get_gateway, has_active_plan, mark_failed, mark_paid
from zaban.services.settings_store import PAYMENT_PROVIDER_KEY, ZARINPAL_MERCHANT_KEY, get_setting
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
        "token_allowance": plan.token_allowance,
    }


def _payment_out(payment: Payment, plan: BillingPlan | None) -> dict:
    return {
        "id": payment.id,
        "plan_name": plan.name if plan else "",
        "amount_toman": payment.amount_toman,
        "status": payment.status,
        "created_at": payment.created_at.isoformat(),
        "confirmed_at": payment.confirmed_at.isoformat() if payment.confirmed_at else None,
        "failure_reason": payment.failure_reason or "",
    }


@router.get("/plans")
def list_plans(db: DBSession = Depends(get_db)) -> list[dict]:
    plans = db.query(BillingPlan).filter(BillingPlan.active.is_(True)).order_by(BillingPlan.price_toman).all()
    return [_plan_out(p) for p in plans]


@router.get("/plan")
def current_plan(zaban_parent: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> dict:
    # The plan the adult is on: its name (from the last confirmed payment), when the paid period began, and when it ends.
    guardian = _guardian_from_cookie(db, zaban_parent)
    last = (
        db.query(Payment)
        .filter(Payment.guardian_id == guardian.id, Payment.status == "confirmed")
        .order_by(Payment.confirmed_at.desc())
        .first()
    )
    plan = db.get(BillingPlan, last.plan_id) if last else None
    active = has_active_plan(guardian)
    expires = guardian.plan_expires_at
    days_left = max(0, math.ceil((expires - utcnow()).total_seconds() / 86400)) if active else 0
    started = guardian.plan_started_at or (last.confirmed_at if last else None)
    allowance = guardian.plan_token_allowance or 0
    used = guardian.plan_tokens_used or 0
    return {
        "has_active_plan": active,
        "plan_name": plan.name if plan else None,
        "plan_name_en": (plan.name_en or plan.name) if plan else None,
        "plan_started_at": started.isoformat() if started else None,
        "plan_expires_at": expires.isoformat() if expires else None,
        "days_left": days_left,
        "token_allowance": allowance,
        "tokens_used": used,
        "tokens_percent": min(100, round(used * 100 / allowance)) if allowance else 0,
    }


@router.get("/payments")
def my_payments(zaban_parent: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> list[dict]:
    # Every payment the adult has made, newest first.
    guardian = _guardian_from_cookie(db, zaban_parent)
    rows = db.query(Payment).filter(Payment.guardian_id == guardian.id).order_by(Payment.created_at.desc()).all()
    return [_payment_out(p, db.get(BillingPlan, p.plan_id)) for p in rows]


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
    # A new plan can be bought only after the current one is finished: its date passed or its tokens are used up.
    if has_active_plan(guardian):
        raise HTTPException(status_code=409, detail="Your current plan is not finished yet")

    gateway = get_gateway(
        get_setting(db, PAYMENT_PROVIDER_KEY, settings.payment_gateway),
        get_setting(db, ZARINPAL_MERCHANT_KEY, settings.zarinpal_merchant_id or ""),
    )
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
        mark_failed(db, payment, "درگاه پرداخت در دسترس نیست. دوباره تلاش کنید.")
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
    if payment is None or payment.gateway != "zarinpal" or payment.gateway_ref != Authority:
        return RedirectResponse(url="/plan?payment=failed", status_code=303)
    if Status != "OK":
        mark_failed(db, payment, "پرداخت در درگاه لغو شد یا انجام نشد.")
        return RedirectResponse(url="/plan?payment=failed", status_code=303)
    merchant = get_setting(db, ZARINPAL_MERCHANT_KEY, settings.zarinpal_merchant_id or "")
    if get_gateway("zarinpal", merchant).verify(payment, Authority):
        # The gateway confirmed the money, so the plan starts now.
        confirm_payment(db, payment, True)
        return RedirectResponse(url="/plan?payment=paid", status_code=303)
    mark_failed(db, payment, "تأیید پرداخت از سوی درگاه انجام نشد.")
    return RedirectResponse(url="/plan?payment=failed", status_code=303)


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
        confirm_payment(db, payment, True)
    else:
        mark_failed(db, payment, "پرداخت آزمایشی ناموفق بود.")
    return {"status": payment.status}
