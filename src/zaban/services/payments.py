from datetime import timedelta
from typing import Protocol

import httpx
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


ZARINPAL_REQUEST_URL = "https://payment.zarinpal.com/pg/v4/payment/request.json"
ZARINPAL_VERIFY_URL = "https://payment.zarinpal.com/pg/v4/payment/verify.json"
ZARINPAL_PAY_URL = "https://payment.zarinpal.com/pg/StartPay/{authority}"


class ZarinPalGateway:
    # ZarinPal v4 REST API. The merchant ID comes from the environment; the server asks ZarinPal to verify every payment.
    name = "zarinpal"

    def __init__(self, merchant_id: str | None, callback_url: str) -> None:
        self.merchant_id = merchant_id
        self.callback_url = callback_url

    def start(self, payment: Payment) -> str:
        if not self.merchant_id:
            raise HTTPException(status_code=503, detail="The payment gateway is not ready yet")
        response = httpx.post(
            ZARINPAL_REQUEST_URL,
            json={
                "merchant_id": self.merchant_id,
                "amount": payment.amount_toman * 10,  # ZarinPal takes rials; prices are stored in toman
                "callback_url": f"{self.callback_url}?payment_id={payment.id}",
                "description": "zaban subscription",
            },
            timeout=15,
        )
        data = (response.json() or {}).get("data") or {}
        if response.status_code != 200 or data.get("code") != 100:
            raise HTTPException(status_code=502, detail="The payment gateway did not accept the request")
        payment.gateway_ref = data["authority"]
        return ZARINPAL_PAY_URL.format(authority=data["authority"])

    def verify(self, payment: Payment, authority: str) -> bool:
        # Only ZarinPal can say a payment succeeded. The return address alone is never trusted.
        if not self.merchant_id:
            return False
        response = httpx.post(
            ZARINPAL_VERIFY_URL,
            json={"merchant_id": self.merchant_id, "amount": payment.amount_toman * 10, "authority": authority},
            timeout=15,
        )
        data = (response.json() or {}).get("data") or {}
        return response.status_code == 200 and data.get("code") in (100, 101)


def get_gateway(provider: str) -> PaymentGateway:
    # The provider is chosen in the admin panel. Its secret keys are read from the environment, never from the panel.
    if provider == "zarinpal":
        return ZarinPalGateway(settings.zarinpal_merchant_id, f"{settings.public_base_url}/v1/web/billing/zarinpal/callback")
    if settings.environment == "production":
        raise HTTPException(status_code=503, detail="The payment gateway is not ready yet")
    return FakeGateway()


def mark_paid(db: DBSession, payment: Payment) -> None:
    # The buyer says they paid. The plan waits for an administrator to confirm it, so nothing is extended yet.
    if payment.status == "pending":
        payment.status = "paid"
        db.commit()


def confirm_payment(db: DBSession, payment: Payment, ok: bool) -> None:
    # Only the server decides this. A confirmed payment extends the guardian's plan period.
    if payment.status not in ("pending", "paid"):
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
