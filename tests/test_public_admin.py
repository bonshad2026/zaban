import os
from datetime import timedelta

from fastapi.testclient import TestClient

from zaban.db import SessionLocal
from zaban.main import app
from zaban.models import Guardian, utcnow
from zaban.services.sms import dev_outbox

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def test_public_pages_are_served_without_sign_in(client):
    for path in ["/", "/signup", "/demo", "/consult", "/admin"]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert "text/html" in response.headers["content-type"]


def test_consult_request_needs_no_sign_in(client):
    response = client.post(
        "/v1/public/consult",
        json={"name": "Parisa", "phone": "+98 912 555 0101", "message": "How does it work?", "preferred_time": "evenings"},
    )
    assert response.status_code == 201, response.text


def test_consult_request_rejects_a_bad_number(client):
    response = client.post("/v1/public/consult", json={"name": "Parisa", "phone": "12345678"})
    assert response.status_code == 400


def test_admin_pages_refuse_without_sign_in(client):
    assert client.get("/v1/admin/api/consults").status_code == 401
    assert client.get("/v1/admin/api/adults").status_code == 401


def test_admin_rejects_a_wrong_password(client):
    assert client.post("/v1/admin/api/login", json={"password": "not-it"}).status_code == 401


def test_admin_sees_consult_requests_and_updates_their_status(client):
    client.post(
        "/v1/public/consult",
        json={"name": "Reza", "phone": "09121110099", "message": "Price?"},
    )
    admin = TestClient(app)
    _admin(admin)
    rows = admin.get("/v1/admin/api/consults").json()
    mine = next(r for r in rows if r["phone"] == "09121110099")
    assert mine["status"] == "new"
    assert admin.post(f"/v1/admin/api/consults/{mine['id']}/status", json={"status": "contacted"}).status_code == 200
    updated = next(r for r in admin.get("/v1/admin/api/consults").json() if r["id"] == mine["id"])
    assert updated["status"] == "contacted"


def test_admin_can_confirm_a_pending_payment_by_hand(client):
    phone = "09121230091"
    adult = TestClient(app)
    adult.post("/v1/web/user/otp/request", json={"phone": phone, "purpose": "signup"})
    code = [c for n, c in dev_outbox() if n == phone][-1]
    adult.post(
        "/v1/web/user/signup",
        json={"phone": phone, "code": code, "full_name": "Manual", "password": "manual-pass-1", "age_confirmed": True},
    )
    plans = adult.get("/v1/web/billing/plans").json()
    paid = adult.post("/v1/web/billing/checkout", json={"plan_id": plans[0]["id"]}).json()

    admin = TestClient(app)
    _admin(admin)
    pending = [p for p in admin.get("/v1/admin/api/payments?status=pending").json() if p["id"] == paid["payment_id"]]
    assert pending, "the new payment should be listed as pending"
    decided = admin.post(f"/v1/admin/api/payments/{paid['payment_id']}/decision", json={"ok": True})
    assert decided.json()["status"] == "confirmed"
    assert adult.get("/v1/web/me?role=parent").json()["has_active_plan"] is True
    # The plan's days are added to the adult's plan period when the payment is confirmed.
    with SessionLocal() as db:
        guardian = db.query(Guardian).filter(Guardian.phone == phone).one()
        remaining = guardian.plan_expires_at - utcnow()
    assert abs(remaining - timedelta(days=plans[0]["days"])) < timedelta(minutes=5)


def test_admin_can_add_and_switch_off_a_plan(client):
    admin = TestClient(app)
    _admin(admin)
    created = admin.post(
        "/v1/admin/api/plans", json={"name": "Trial", "description": "", "price_toman": 50000, "days": 7}
    )
    assert created.status_code == 201
    plan_id = created.json()["id"]
    assert admin.post(f"/v1/admin/api/plans/{plan_id}/active", json={"active": False}).status_code == 200
    public = client.get("/v1/web/billing/plans").json()
    assert all(p["id"] != plan_id for p in public)
