from datetime import timedelta
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy.orm import Session as DBSession

from zaban.config import settings
from zaban.models import BillingPlan, Guardian, Payment, utcnow


class PaymentGateway(Protocol):
    name: str

    def start(self, payment: Payment) -> str:
        """Create the payment at the gateway and return the address the buyer is sent to."""
        ...


class FakeGateway:
    # Development only. The buyer sees a local page with "pay" and "fail" buttons instead of a bank page.
    name = "fake"

    def start(self, payment: Payment) -> str:
        return f"/dev/pay/{payment.id}"


class ZarinPalGateway:
    # Placeholder. The real request and verify calls are added once the merchant ID is available.
    name = "zarinpal"

    def start(self, payment: Payment) -> str:
        raise HTTPException(status_code=503, detail="The payment gateway is not ready yet")


def get_gateway() -> PaymentGateway:
    if settings.payment_gateway == "zarinpal":
        return ZarinPalGateway()
    if settings.environment == "production":
        raise HTTPException(status_code=503, detail="The payment gateway is not ready yet")
    return FakeGateway()


def confirm_payment(db: DBSession, payment: Payment, ok: bool) -> None:
    # Only the server decides this. A confirmed payment extends the guardian's plan period.
    if payment.status != "pending":
        return
    if not ok:
        payment.status = "failed"
        db.commit()
        return

    plan = db.get(BillingPlan, payment.plan_id)
    guardian = db.get(Guardian, payment.guardian_id)
    now = utcnow()
    start = max(now, guardian.plan_expires_at) if guardian.plan_expires_at else now
    guardian.plan_expires_at = start + timedelta(days=plan.days)
    payment.status = "confirmed"
    payment.confirmed_at = now
    db.commit()


def has_active_plan(guardian: Guardian) -> bool:
    return guardian.plan_expires_at is not None and guardian.plan_expires_at > utcnow()


def require_plan(guardian: Guardian | None) -> None:
    # Adults without an active plan cannot use the service. They must choose and pay for a plan first.
    if guardian is None or not has_active_plan(guardian):
        raise HTTPException(status_code=402, detail="Choose a plan first to use the service")
