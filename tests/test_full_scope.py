import base64
import io
import os
import zipfile

from zaban.db import SessionLocal
from zaban.models import LearnerDetails, Student, StudentProgress
from zaban.services.sessions import build_system_prompt

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
STUDENT_USERNAME = os.environ["ZABAN_DEMO_STUDENT_USERNAME"]
STUDENT_PASSWORD = os.environ["ZABAN_DEMO_STUDENT_PASSWORD"]
PARENT_PHONE = os.environ["ZABAN_DEMO_PARENT_PHONE"]
PARENT_PASSWORD = os.environ["ZABAN_DEMO_PARENT_PASSWORD"]
API_KEY = os.environ["ZABAN_DEMO_API_KEY"]


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def _student(client) -> str:
    body = {"username": STUDENT_USERNAME, "password": STUDENT_PASSWORD}
    assert client.post("/v1/web/student/login", json=body).status_code == 200
    with SessionLocal() as db:
        return db.query(Student).filter(Student.username == STUDENT_USERNAME).one().id


def _parent(client) -> None:
    body = {"phone": PARENT_PHONE, "password": PARENT_PASSWORD}
    assert client.post("/v1/web/user/login", json=body).status_code == 200


# ----- Pages -----

def test_landing_offers_learner_sign_in_from_header(client):
    html = client.get("/").text
    # The sign-in menu in the header links to the learner page. The admin page is not linked publicly.
    assert 'href="/student"' in html


def test_student_page_has_the_learner_tools(client):
    html = client.get("/student").text
    for section in ("tab-profile", "tab-progress", "tab-help", "tab-test", "tab-payments"):
        assert f'id="{section}"' in html
    assert "student-tools.js" in html


def test_parent_page_has_the_child_details_card(client):
    html = client.get("/parent").text
    assert 'id="cdForm"' in html and "parent-tools.js" in html


def test_admin_page_has_the_new_tabs(client):
    html = client.get("/admin").text
    for tab in ("overview", "helpcontent", "settings", "build"):
        assert f'data-tab="{tab}"' in html


def test_static_scripts_are_served(client):
    for path in ("/static/js/student-tools.js", "/static/js/parent-tools.js", "/static/js/cooperation.js"):
        assert client.get(path).status_code == 200


# ----- Learner details and the lesson prompt -----

def test_learner_saves_and_reads_their_details(client):
    _student(client)
    body = {"age": 11, "gender": "female", "grade": "5", "attributes": "kind", "conversation_style": "story",
            "response_style": "playful", "level_sample": "I like cats.", "free_text": "I love drawing"}
    assert client.put("/v1/web/student/details", json=body).status_code == 200
    details = client.get("/v1/web/student/details").json()["details"]
    assert details["age"] == 11 and details["conversation_style"] == "story" and details["free_text"] == "I love drawing"


def test_partial_details_update_keeps_other_fields(client):
    _student(client)
    client.put("/v1/web/student/details", json={"grade": "6"})
    client.put("/v1/web/student/details", json={"free_text": "football"})
    details = client.get("/v1/web/student/details").json()["details"]
    assert details["grade"] == "6" and details["free_text"] == "football"


def test_details_reject_unknown_style(client):
    _student(client)
    assert client.put("/v1/web/student/details", json={"conversation_style": "karaoke"}).status_code == 422
    assert client.put("/v1/web/student/details", json={"age": 150}).status_code == 422


def test_learner_sets_their_own_level(client):
    _student(client)
    assert client.put("/v1/web/student/level", json={"cefr_level": "B1"}).json()["cefr_level"] == "B1"
    assert client.put("/v1/web/student/level", json={"cefr_level": "Z9"}).status_code == 422


def test_prompt_modes_choose_the_sources(client):
    with SessionLocal() as db:
        student = db.query(Student).filter(Student.username == STUDENT_USERNAME).one()
        db.expunge(student)
    details = LearnerDetails(student_id=student.id, free_text="FOOTBALL_TOKEN")
    kwargs = {"details": details, "global_prompt": "GENERAL_TOKEN", "course_note": "COURSE_TOKEN", "past_notes": "PAST_TOKEN"}
    student_only = build_system_prompt(student, None, "warm_up", 10, mode="student", **kwargs)
    general_only = build_system_prompt(student, None, "warm_up", 10, mode="general", **kwargs)
    student_db = build_system_prompt(student, None, "warm_up", 10, mode="student_db", **kwargs)
    everything = build_system_prompt(student, None, "warm_up", 10, mode="all", **kwargs)
    assert "FOOTBALL_TOKEN" in student_only and "GENERAL_TOKEN" not in student_only and "COURSE_TOKEN" not in student_only
    assert "GENERAL_TOKEN" in general_only and "FOOTBALL_TOKEN" not in general_only
    assert "COURSE_TOKEN" in student_db and "PAST_TOKEN" in student_db and "GENERAL_TOKEN" not in student_db
    assert all(t in everything for t in ("FOOTBALL_TOKEN", "GENERAL_TOKEN", "COURSE_TOKEN", "PAST_TOKEN"))


def test_prompt_contains_the_seventy_percent_rule(client):
    with SessionLocal() as db:
        student = db.query(Student).filter(Student.username == STUDENT_USERNAME).one()
        db.expunge(student)
    assert "70 percent" in build_system_prompt(student, None, "main_practice", 10)


def test_admin_sets_prompt_mode_and_expected_output(client):
    _admin(client)
    body = {"prompt_mode": "student_db", "expected_output": "Use past words", "payment_provider": "fake"}
    assert client.post("/v1/admin/api/settings", json=body).status_code == 200
    saved = client.get("/v1/admin/api/settings").json()
    assert saved["prompt_mode"] == "student_db" and saved["expected_output"] == "Use past words"
    assert "anthropic_api_key_set" in saved["secrets"]
    assert client.post("/v1/admin/api/settings", json={"prompt_mode": "random"}).status_code == 422
    client.post("/v1/admin/api/settings", json={"prompt_mode": "all", "expected_output": ""})


def test_admin_reads_a_learner_detail(client):
    student_id = _student(client)
    _admin(client)
    detail = client.get(f"/v1/admin/api/learners/{student_id}").json()
    assert detail["username"] == STUDENT_USERNAME
    assert "progress" in detail and "self_tests" in detail


# ----- Progress, stages and evaluations -----

def test_learner_progress_is_shown_with_stages(client):
    student_id = _student(client)
    response = client.get("/v1/web/student/progress")
    assert response.status_code == 200
    data = response.json()
    assert "stages" in data and "percent" in data and "session_number" in data
    with SessionLocal() as db:
        progress = db.get(StudentProgress, student_id)
        assert progress is None or progress.position >= 0


def test_admin_sets_course_duration_and_stage(client):
    _admin(client)
    programs = client.get("/v1/admin/api/programs").json()["programs"]
    program = programs[0]
    assert client.post(f"/v1/admin/api/programs/{program['id']}/duration", json={"duration_months": 24}).status_code == 200
    assert client.post(f"/v1/admin/api/programs/{program['id']}/duration", json={"duration_months": 0}).status_code == 422
    body = {"title": program["items"][0]["title"], "stage": "Stage 1", "activity": "", "phrases": []}
    assert client.put(f"/v1/admin/api/programs/{program['id']}/items/1", json=body).status_code == 200
    refreshed = client.get("/v1/admin/api/programs").json()["programs"][0]
    assert refreshed["duration_months"] == 24
    assert refreshed["items"][0]["stage"] == "Stage 1"


# ----- Self-test: owner-only and the admin prompt -----

def test_self_test_starts_after_the_admin_changes_its_prompt(client):
    _admin(client)
    assert client.post("/v1/admin/api/self-test-prompt", json={"text": "Be a strict examiner."}).status_code == 200
    _student(client)
    created = client.post("/v1/web/student/self-tests", json={"kind": "qa", "skill": "writing", "minutes": 5})
    assert created.status_code == 201


# ----- Help content: admin file upload, learner file access -----

def test_admin_help_content_file_needs_a_known_mime(client):
    _admin(client)
    body = {"title": "Bad type", "category": "story", "age_band": "T", "level": "A1",
            "data_base64": base64.b64encode(b"x").decode(), "mime": "application/x-msdownload"}
    assert client.post("/v1/admin/api/help-content", json=body).status_code == 422


def test_help_content_filter_by_category(client):
    _student(client)
    assert client.get("/v1/web/student/help-content?category=podcast").status_code == 200


# ----- Parent view of a child -----

def test_parent_cannot_read_another_familys_child(client):
    _parent(client)
    assert client.get("/v1/web/parent/children/not-my-child/details").status_code == 404
    assert client.get("/v1/web/parent/children/not-my-child/progress").status_code == 404


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


# ----- Build download and migration output -----

def test_admin_build_download_is_a_zip_without_secrets(client):
    _admin(client)
    response = client.post("/v1/admin/api/build")
    assert response.status_code == 200, response.text
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = archive.namelist()
    assert "schema/schema_changes.sql" in names
    assert "database/data.json" in names
    data = archive.read("database/data.json").decode("utf-8")
    assert "password_hash" not in data and "api_key_hash" not in data
    assert "otp_codes" not in data


def test_build_rejects_a_ref_that_looks_like_an_option(client):
    _admin(client)
    assert client.post("/v1/admin/api/build?since=--output=x").status_code == 422


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
                                            "subject": "Kids class", "contact_permission": True})
    _admin(client)
    row = next(r for r in client.get("/v1/admin/api/consults").json() if r["phone"] == "09121230003")
    assert row["last_name"] == "Hosseini" and row["subject"] == "Kids class" and row["contact_permission"] is True


# ----- Student sign-in page links to the parent sign-in -----

def test_student_page_links_to_parent_sign_in(client):
    assert 'href="/parent"' in client.get("/student").text


# ----- A lesson needs the level and the basic profile first -----

def test_lesson_is_refused_until_the_profile_is_complete(client):
    headers = {"x-api-key": API_KEY}
    student_id = client.post("/v1/students", json={"age_band": "11-14", "display_name": "Gate"}, headers=headers).json()["id"]
    assert client.post(f"/v1/students/{student_id}/consent", json={"accepted": True}, headers=headers).status_code == 201
    refused = client.post(f"/v1/students/{student_id}/sessions", json={"duration_minutes": 5}, headers=headers)
    assert refused.status_code == 409
    assert "Complete the profile" in refused.json()["detail"]


# ----- One item is one lesson: its concepts, and the pace set by the learner's plan -----

def test_admin_saves_the_concepts_of_one_lesson(client):
    _admin(client)
    program = client.get("/v1/admin/api/programs").json()["programs"][0]
    body = {"title": "Greetings", "stage": "Stage 1", "concepts": ["hello", "good morning"], "activity": "", "phrases": []}
    assert client.put(f"/v1/admin/api/programs/{program['id']}/items/1", json=body).status_code == 200
    item = client.get("/v1/admin/api/programs").json()["programs"][0]["items"][0]
    assert item["concepts"] == ["hello", "good morning"]


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


def _parent_payment(client, monkeypatch, sent: list):
    from zaban.services import payments as payments_module

    import dataclasses

    test_settings = dataclasses.replace(payments_module.settings, zarinpal_merchant_id="merchant-test-id",
                                        public_base_url="http://site.test")
    monkeypatch.setattr(payments_module, "settings", test_settings)

    def fake_post(url, json, timeout):
        sent.append((url, json))
        if url.endswith("/request.json"):
            return _FakeResponse(200, {"data": {"code": 100, "authority": "A0000000001"}})
        return _FakeResponse(200, {"data": {"code": 100}})

    monkeypatch.setattr(payments_module.httpx, "post", fake_post)
    _parent(client)
    plan_id = client.get("/v1/web/billing/plans").json()[0]["id"]
    return client.post("/v1/web/billing/checkout", json={"plan_id": plan_id})


def test_zarinpal_checkout_sends_the_amount_in_rials_and_a_callback(client, monkeypatch):
    from zaban.services import payments as payments_module

    sent: list = []
    _admin(client)
    client.post("/v1/admin/api/settings", json={"payment_provider": "zarinpal"})
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
        client.post("/v1/admin/api/settings", json={"payment_provider": "fake"})


def test_zarinpal_callback_marks_paid_only_after_verification(client, monkeypatch):
    from zaban.services import payments as payments_module
    from zaban.db import SessionLocal
    from zaban.models import Payment

    sent: list = []
    _admin(client)
    client.post("/v1/admin/api/settings", json={"payment_provider": "zarinpal"})
    try:
        payment_id = _parent_payment(client, monkeypatch, sent).json()["payment_id"]
        ok = client.get(f"/v1/web/billing/zarinpal/callback?payment_id={payment_id}&Authority=A0000000001&Status=OK",
                        follow_redirects=False)
        assert ok.status_code == 303 and "payment=paid" in ok.headers["location"]
        with SessionLocal() as db:
            assert db.get(Payment, payment_id).status == "paid"
        # A wrong authority, or a cancelled payment, never reaches ZarinPal and is never marked paid.
        bad = client.get(f"/v1/web/billing/zarinpal/callback?payment_id={payment_id}&Authority=WRONG&Status=OK",
                         follow_redirects=False)
        assert "payment=failed" in bad.headers["location"]
    finally:
        _admin(client)
        client.post("/v1/admin/api/settings", json={"payment_provider": "fake"})


def test_zarinpal_refuses_when_the_verification_fails(client, monkeypatch):
    from zaban.services import payments as payments_module
    from zaban.db import SessionLocal
    from zaban.models import Payment

    sent: list = []
    _admin(client)
    client.post("/v1/admin/api/settings", json={"payment_provider": "zarinpal"})
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
        client.post("/v1/admin/api/settings", json={"payment_provider": "fake"})
