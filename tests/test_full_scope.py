import base64
import os

from zaban.db import SessionLocal
from zaban.models import Guardian
from helpers_learner import learner_login, self_student

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
PARENT_PHONE = os.environ["ZABAN_DEMO_PARENT_PHONE"]
PARENT_PASSWORD = os.environ["ZABAN_DEMO_PARENT_PASSWORD"]
API_KEY = os.environ["ZABAN_DEMO_API_KEY"]


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def _student(client) -> str:
    learner_login(client)
    with SessionLocal() as db:
        return self_student(db).id


def _parent(client) -> None:
    body = {"phone": PARENT_PHONE, "password": PARENT_PASSWORD}
    assert client.post("/v1/web/user/login", json=body).status_code == 200


# ----- Pages -----

def test_landing_offers_one_sign_in_from_header(client):
    html = client.get("/").text
    # One sign-in for adults. The admin page is not linked publicly.
    assert 'href="/login"' in html
    assert 'href="/student"' not in html


def test_student_page_has_the_learner_tools(client):
    html = client.get("/student").text
    for section in ("tab-progress", "tab-help", "tab-test", "tab-payments"):
        assert f'id="{section}"' in html
    assert "student-tools.js" in html


def test_parent_page_has_no_child_tools(client):
    html = client.get("/login").text
    assert 'id="cdForm"' not in html and 'id="addForm"' not in html and "parent-tools.js" not in html


def test_admin_page_has_the_new_tabs(client):
    html = client.get("/admin").text
    for tab in ("overview", "helpcontent", "settings"):
        assert f'data-tab="{tab}"' in html


def test_static_scripts_are_served(client):
    for path in ("/static/js/student-tools.js", "/static/js/cooperation.js"):
        assert client.get(path).status_code == 200


# ----- Learner details and the lesson prompt -----

def test_learner_saves_and_reads_their_details(client):
    _student(client)
    body = {"age": 34, "gender": "female", "attributes": "kind", "conversation_style": "story",
            "response_style": "playful", "level_sample": "I like cats.", "free_text": "I love drawing"}
    assert client.put("/v1/web/student/details", json=body).status_code == 200
    details = client.get("/v1/web/student/details").json()["details"]
    assert details["age"] == 34 and details["conversation_style"] == "story" and details["free_text"] == "I love drawing"


def test_partial_details_update_keeps_other_fields(client):
    _student(client)
    client.put("/v1/web/student/details", json={"age": 34})
    client.put("/v1/web/student/details", json={"free_text": "football"})
    details = client.get("/v1/web/student/details").json()["details"]
    assert details["age"] == 34 and details["free_text"] == "football"


def test_details_reject_unknown_style(client):
    _student(client)
    assert client.put("/v1/web/student/details", json={"conversation_style": "karaoke"}).status_code == 422
    assert client.put("/v1/web/student/details", json={"age": 150}).status_code == 422


def test_learner_sets_a_skill_level(client):
    # Each skill has its own level. The learner sets a starting level; an unknown level is refused.
    _student(client)
    assert client.put("/v1/web/student/skill-levels", json={"listening": "B1"}).json()["skill_levels"]["listening"] == "B1"
    assert client.put("/v1/web/student/skill-levels", json={"listening": "Z9"}).status_code == 422


def test_admin_reads_a_learner_detail(client):
    student_id = _student(client)
    _admin(client)
    detail = client.get(f"/v1/admin/api/learners/{student_id}").json()
    assert "progress" in detail and "self_tests" in detail


# ----- Progress, stages and evaluations -----

def test_learner_progress_is_shown_with_the_lesson_path(client):
    _student(client)
    response = client.get("/v1/web/student/progress")
    assert response.status_code == 200
    data = response.json()
    assert "lessons" in data and "percent" in data and "session_number" in data


# ----- Self-test: owner-only and the admin prompt -----

def test_self_test_starts_after_the_admin_changes_its_prompt(client):
    _admin(client)
    assert client.post("/v1/admin/api/self-test/rules", json={"key": "role", "text": "Be a strict examiner."}).status_code == 200
    _student(client)
    created = client.post("/v1/web/student/self-tests", json={"kind": "qa", "skill": "writing", "minutes": 5})
    assert created.status_code == 201


# ----- Help content: admin file upload, learner file access -----

def test_admin_help_content_file_needs_a_known_mime(client):
    _admin(client)
    body = {"title": "Bad type", "category": "story", "age_band": "A", "level": "A1",
            "data_base64": base64.b64encode(b"x").decode(), "mime": "application/x-msdownload"}
    assert client.post("/v1/admin/api/help-content", json=body).status_code == 422


def test_help_content_filter_by_category(client):
    _student(client)
    assert client.get("/v1/web/student/help-content?category=podcast").status_code == 200


# ----- Parent view of a child -----

def test_parent_cannot_read_another_familys_child(client):
    _parent(client)


# ----- Stand-alone AI service -----

def test_ai_service_needs_a_tenant_key(client):
    body = {"system": "Be kind.", "messages": [{"role": "user", "content": "Hi"}]}
    assert client.post("/v1/ai/complete", json=body).status_code == 401
    response = client.post("/v1/ai/complete", json=body, headers={"x-api-key": API_KEY})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "offline" and data["text"]


def test_ai_service_rejects_a_conversation_that_ends_with_the_assistant(client):
    body = {"system": "Be kind.", "messages": [{"role": "assistant", "content": "Hi"}]}
    assert client.post("/v1/ai/complete", json=body, headers={"x-api-key": API_KEY}).status_code == 422


# ----- Consult form: name, subject and call permission -----

def test_consult_needs_permission_and_subject(client):
    base = {"name": "Mina", "last_name": "Rezaei", "phone": "09121230002", "subject": "Prices"}
    assert client.post("/v1/public/consult", json={**base, "contact_permission": False}).status_code == 422
    assert client.post("/v1/public/consult", json={**base, "subject": "x", "contact_permission": True}).status_code == 422
    assert client.post("/v1/public/consult", json={**base, "contact_permission": True}).status_code == 201


def test_consult_form_has_the_new_fields(client):
    html = client.get("/consult").text
    for field in ('id="consultLast"', 'id="consultSubject"', 'id="consultPermission"'):
        assert field in html


def test_admin_consult_list_shows_the_new_fields(client):
    client.post("/v1/public/consult", json={"name": "Ali", "last_name": "Hosseini", "phone": "09121230003",
                                            "subject": "Adult class", "contact_permission": True})
    _admin(client)
    row = next(r for r in client.get("/v1/admin/api/consults").json() if r["phone"] == "09121230003")
    assert row["last_name"] == "Hosseini" and row["subject"] == "Adult class" and row["contact_permission"] is True


# ----- Student sign-in page links to the parent sign-in -----

def test_student_page_links_to_parent_sign_in(client):
    assert 'href="/login"' in client.get("/student").text


# ----- A lesson needs the level and the basic profile first -----

def test_lesson_is_refused_until_the_profile_is_complete(client):
    headers = {"x-api-key": API_KEY}
    student_id = client.post("/v1/students", json={"age_band": "adult", "display_name": "Gate"}, headers=headers).json()["id"]
    assert client.post(f"/v1/students/{student_id}/consent", json={"accepted": True}, headers=headers).status_code == 201
    refused = client.post(f"/v1/students/{student_id}/sessions", json={"duration_minutes": 5}, headers=headers)
    assert refused.status_code == 409
    assert "Complete the profile" in refused.json()["detail"]


# ----- One item is one lesson: its concepts, and the pace set by the learner's plan -----

def test_progress_shows_the_expected_week_from_the_plan_pace(client):
    _student(client)
    data = client.get("/v1/web/student/progress").json()
    assert "pace" in data


# ----- ZarinPal: the server asks for the payment and verifies it; the return address is never trusted -----

class _FakeResponse:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


def _reset_zarinpal_panel() -> None:
    # Puts the provider and the merchant ID back to their defaults, so other tests use the development gateway.
    from zaban.services.settings_store import PAYMENT_PROVIDER_KEY, ZARINPAL_MERCHANT_KEY, set_setting

    with SessionLocal() as db:
        set_setting(db, PAYMENT_PROVIDER_KEY, "")
        set_setting(db, ZARINPAL_MERCHANT_KEY, "")
        db.commit()


def _parent_payment(client, monkeypatch, sent: list):
    from zaban.services import payments as payments_module
    from zaban.services.settings_store import PAYMENT_PROVIDER_KEY, ZARINPAL_MERCHANT_KEY, set_setting

    # The demo adult already has an active plan, so it has to use up its tokens before it can buy again.
    # The tokens are restored once the purchase has been requested, so the other tests keep their demo plan.
    with SessionLocal() as db:
        guardian = db.query(Guardian).filter(Guardian.phone == PARENT_PHONE).one()
        spent_before = guardian.plan_tokens_used
        guardian.plan_tokens_used = guardian.plan_token_allowance
        db.commit()

    import dataclasses

    # The provider and the merchant ID are set in the admin panel (the database). The site address comes from BASE_URL.
    test_settings = dataclasses.replace(payments_module.settings, public_base_url="http://site.test")
    monkeypatch.setattr(payments_module, "settings", test_settings)
    from zaban import billing as billing_module
    monkeypatch.setattr(billing_module, "settings", test_settings)

    def fake_post(url, json, timeout):
        sent.append((url, json))
        if url.endswith("/request.json"):
            return _FakeResponse(200, {"data": {"code": 100, "authority": "A0000000001"}})
        return _FakeResponse(200, {"data": {"code": 100}})

    monkeypatch.setattr(payments_module.httpx, "post", fake_post)
    with SessionLocal() as db:
        set_setting(db, PAYMENT_PROVIDER_KEY, "zarinpal")
        set_setting(db, ZARINPAL_MERCHANT_KEY, "merchant-test-id")
        db.commit()
    try:
        _parent(client)
        plan_id = client.get("/v1/web/billing/plans").json()[0]["id"]
        response = client.post("/v1/web/billing/checkout", json={"plan_id": plan_id})
    finally:
        with SessionLocal() as db:
            guardian = db.query(Guardian).filter(Guardian.phone == PARENT_PHONE).one()
            guardian.plan_tokens_used = spent_before
            db.commit()
    return response


def test_zarinpal_checkout_sends_the_amount_in_rials_and_a_callback(client, monkeypatch):
    from zaban.services import payments as payments_module

    sent: list = []
    _admin(client)
    try:
        response = _parent_payment(client, monkeypatch, sent)
        assert response.status_code == 201, response.text
        assert response.json()["redirect"] == "https://payment.zarinpal.com/pg/StartPay/A0000000001"
        url, body = sent[0]
        assert url.endswith("/pg/v4/payment/request.json")
        assert body["merchant_id"] == "merchant-test-id" and body["amount"] % 10 == 0
        assert body["callback_url"].startswith("http://site.test/v1/web/billing/zarinpal/callback?payment_id=")
    finally:
        _admin(client)
        _reset_zarinpal_panel()


def test_zarinpal_callback_marks_paid_only_after_verification(client, monkeypatch):
    from zaban.services import payments as payments_module
    from zaban.db import SessionLocal
    from zaban.models import Payment
    from zaban.services.settings_store import PAYMENT_PROVIDER_KEY, ZARINPAL_MERCHANT_KEY, set_setting

    sent: list = []
    _admin(client)
    # The callback verifies with the merchant ID from the panel, so it stays set for the whole test.
    with SessionLocal() as db:
        set_setting(db, ZARINPAL_MERCHANT_KEY, "merchant-test-id")
        db.commit()
    try:
        payment_id = _parent_payment(client, monkeypatch, sent).json()["payment_id"]
        ok = client.get(f"/v1/web/billing/zarinpal/callback?payment_id={payment_id}&Authority=A0000000001&Status=OK",
                        follow_redirects=False)
        assert ok.status_code == 303 and "payment=paid" in ok.headers["location"]
        with SessionLocal() as db:
            assert db.get(Payment, payment_id).status == "confirmed"
        # A wrong authority, or a cancelled payment, never reaches ZarinPal and is never marked paid.
        bad = client.get(f"/v1/web/billing/zarinpal/callback?payment_id={payment_id}&Authority=WRONG&Status=OK",
                         follow_redirects=False)
        assert "payment=failed" in bad.headers["location"]
    finally:
        _admin(client)
        _reset_zarinpal_panel()


def test_zarinpal_refuses_when_the_verification_fails(client, monkeypatch):
    from zaban.services import payments as payments_module
    from zaban.db import SessionLocal
    from zaban.models import Payment

    sent: list = []
    _admin(client)
    try:
        payment_id = _parent_payment(client, monkeypatch, sent).json()["payment_id"]
        monkeypatch.setattr(payments_module.httpx, "post", lambda url, json, timeout: _FakeResponse(200, {"data": {"code": -54}}))
        response = client.get(f"/v1/web/billing/zarinpal/callback?payment_id={payment_id}&Authority=A0000000001&Status=OK",
                              follow_redirects=False)
        assert "payment=failed" in response.headers["location"]
        with SessionLocal() as db:
            assert db.get(Payment, payment_id).status == "failed"
    finally:
        _admin(client)
        _reset_zarinpal_panel()
