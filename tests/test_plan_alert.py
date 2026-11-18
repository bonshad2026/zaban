# The learner's plan alert (GET /v1/web/student/plan-status): what the learner is told at the top of the learner page.
from datetime import timedelta

import pytest

from helpers_learner import PARENT_PHONE, learner_login
from zaban.db import SessionLocal
from zaban.models import Guardian, utcnow
from zaban.services.settings_store import set_setting

@pytest.fixture(autouse=True)
def _restore_thresholds(client):
    # The tests change the administrator's thresholds; put the defaults back after each one.
    yield
    _set_threshold("partner_token_warn_remaining", "20,10")
    _set_threshold("partner_expiry_warn_days", "3")


ACTIVE = {"plan_expires_at": utcnow() + timedelta(days=60), "plan_token_allowance": 1000, "plan_tokens_used": 0}


def _set_plan(**fields):
    with SessionLocal() as db:
        guardian = db.query(Guardian).filter(Guardian.phone == PARENT_PHONE).one()
        for name, value in fields.items():
            setattr(guardian, name, value)
        db.commit()


def _login_with_plan(client, **fields):
    # Sign-in needs an active plan, so the plan is set before signing in and then changed to the case under test.
    _set_plan(**ACTIVE)
    learner_login(client)
    _set_plan(**fields)


def _set_threshold(key, value):
    with SessionLocal() as db:
        set_setting(db, key, value)
        db.commit()


def test_no_plan_is_announced(client):
    _login_with_plan(client, plan_expires_at=None, plan_token_allowance=0, plan_tokens_used=0)
    body = client.get("/v1/web/student/plan-status").json()
    assert body["has_active_plan"] is False
    assert body["alerts"] == [{"kind": "no_plan"}]


def test_expired_plan_is_announced(client):
    _login_with_plan(client, plan_expires_at=utcnow() - timedelta(days=1), plan_token_allowance=1000, plan_tokens_used=10)
    assert client.get("/v1/web/student/plan-status").json()["alerts"] == [{"kind": "expired"}]


def test_tokens_used_up_is_announced(client):
    _login_with_plan(client, plan_expires_at=utcnow() + timedelta(days=20), plan_token_allowance=1000, plan_tokens_used=1000)
    assert client.get("/v1/web/student/plan-status").json()["alerts"] == [{"kind": "tokens_used"}]


def test_low_tokens_and_expiry_use_the_admin_thresholds(client):
    _set_threshold("partner_token_warn_remaining", "30")
    _set_threshold("partner_expiry_warn_days", "3")
    _login_with_plan(client, plan_expires_at=utcnow() + timedelta(days=2), plan_token_allowance=1000, plan_tokens_used=800)
    body = client.get("/v1/web/student/plan-status").json()
    assert body["has_active_plan"] is True
    assert body["tokens_remaining_percent"] == 20
    kinds = {alert["kind"]: alert for alert in body["alerts"]}
    assert kinds["tokens"]["remaining_percent"] == 20
    assert kinds["expiry"]["days_left"] in (1, 2)


def test_healthy_plan_has_no_alert(client):
    _set_threshold("partner_token_warn_remaining", "20,10")
    _set_threshold("partner_expiry_warn_days", "3")
    _login_with_plan(client, plan_expires_at=utcnow() + timedelta(days=60), plan_token_allowance=1000, plan_tokens_used=100)
    assert client.get("/v1/web/student/plan-status").json()["alerts"] == []
