from fastapi.testclient import TestClient

from zaban.db import SessionLocal
from zaban.main import app
from zaban.models import Guardian, Payment
from zaban.services.payments import confirm_payment
from zaban.services.sms import dev_outbox


def _adult(phone: str) -> TestClient:
    adult = TestClient(app)
    adult.post("/v1/web/user/otp/request", json={"phone": phone, "purpose": "signup"})
    code = [c for n, c in dev_outbox() if n == phone][-1]
    created = adult.post(
        "/v1/web/user/signup",
        json={"phone": phone, "code": code, "full_name": "Plan Adult", "password": "plan-pass-1"},
    )
    assert created.status_code == 201, created.text
    return adult


def test_plan_is_empty_before_a_payment_and_shows_the_plan_after_one(client):
    adult = _adult("09121230301")
    before = adult.get("/v1/web/billing/plan").json()
    assert before["has_active_plan"] is False
    assert before["plan_name"] is None and before["plan_expires_at"] is None and before["days_left"] == 0

    plan = adult.get("/v1/web/billing/plans").json()[0]
    paid = adult.post("/v1/web/billing/checkout", json={"plan_id": plan["id"]}).json()
    with SessionLocal() as db:
        confirm_payment(db, db.get(Payment, paid["payment_id"]), True)

    after = adult.get("/v1/web/billing/plan").json()
    assert after["has_active_plan"] is True
    assert after["plan_name"] == plan["name"]
    assert after["plan_started_at"] is not None and after["plan_expires_at"] is not None
    assert after["days_left"] == plan["days"]


def test_gender_offers_only_female_and_male(client):
    adult = _adult("09121230302")
    assert adult.put("/v1/web/user/profile", json={"gender": "female"}).status_code == 200
    assert adult.put("/v1/web/user/profile", json={"gender": "male"}).status_code == 200
    assert adult.put("/v1/web/user/profile", json={"gender": "other"}).status_code == 422


def test_payments_list_shows_every_payment_newest_first(client):
    adult = _adult("09121230303")
    plan = adult.get("/v1/web/billing/plans").json()[0]
    assert adult.get("/v1/web/billing/payments").json() == []

    first = adult.post("/v1/web/billing/checkout", json={"plan_id": plan["id"]}).json()
    second = adult.post("/v1/web/billing/checkout", json={"plan_id": plan["id"]}).json()
    rows = adult.get("/v1/web/billing/payments").json()
    assert [r["id"] for r in rows] == [second["payment_id"], first["payment_id"]]
    assert rows[0]["plan_name"] == plan["name"] and rows[0]["status"] == "pending"
    assert rows[0]["amount_toman"] == plan["price_toman"]


def test_a_new_plan_waits_until_the_current_one_is_finished(client):
    adult = _adult("09121230304")
    plan = adult.get("/v1/web/billing/plans").json()[0]
    paid = adult.post("/v1/web/billing/checkout", json={"plan_id": plan["id"]}).json()
    with SessionLocal() as db:
        confirm_payment(db, db.get(Payment, paid["payment_id"]), True)

    # A plan with a date and tokens left cannot be bought again.
    assert adult.post("/v1/web/billing/checkout", json={"plan_id": plan["id"]}).status_code == 409

    # Once the tokens are used up, the plan is finished and a new one can be bought.
    with SessionLocal() as db:
        guardian = db.query(Guardian).filter(Guardian.phone == "09121230304").one()
        guardian.plan_tokens_used = guardian.plan_token_allowance
        db.commit()
    assert adult.get("/v1/web/billing/plan").json()["has_active_plan"] is False
    assert adult.post("/v1/web/billing/checkout", json={"plan_id": plan["id"]}).status_code == 201

