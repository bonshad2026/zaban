import os
import secrets

from fastapi.testclient import TestClient

from zaban.db import SessionLocal
from zaban.main import app
from zaban.models import OtpCode, Student
from zaban.services.otp import normalize_phone
from zaban.services.passwords import hash_password, verify_password
from zaban.services.sms import dev_outbox

# Values come from conftest.py, which generates them for each test run.
PARENT_PHONE = os.environ["ZABAN_DEMO_PARENT_PHONE"]
STUDENT_USERNAME = os.environ["ZABAN_DEMO_STUDENT_USERNAME"]
STUDENT_PASSWORD = os.environ["ZABAN_DEMO_STUDENT_PASSWORD"]
OTHER_PARENT_PHONE = "09121112233"
NEW_CHILD_USERNAME = "web-test-child"
NEW_CHILD_PIN = "4821"


def _demo_student_id() -> str:
    with SessionLocal() as db:
        return db.query(Student).filter(Student.username == STUDENT_USERNAME).one().id


def _sms_code(phone: str) -> str:
    return [code for number, code in dev_outbox() if number == phone][-1]


def _clear_codes(phone: str) -> None:
    # Deletes every code, not only this phone's, so the per-IP limit does not carry over between tests.
    # The phone argument is kept so each test says which number it is about.
    with SessionLocal() as db:
        db.query(OtpCode).delete()
        db.commit()


def _adult_login(client, phone: str = PARENT_PHONE, name: str = "Test Adult"):
    # Clears old codes so the 60-second resend limit does not get in the way of each test.
    _clear_codes(phone)
    assert client.post("/v1/web/user/otp/request", json={"phone": phone}).status_code == 200
    return client.post(
        "/v1/web/user/otp/verify", json={"phone": phone, "code": _sms_code(phone), "full_name": name}
    )


def _buy_plan(client) -> None:
    # Uses the development gateway: checkout, then the fake "pay" button.
    plans = client.get("/v1/web/billing/plans").json()
    paid = client.post("/v1/web/billing/checkout", json={"plan_id": plans[0]["id"]})
    assert paid.status_code == 201, paid.text
    confirmed = client.post(
        "/v1/web/billing/fake/confirm", json={"payment_id": paid.json()["payment_id"], "ok": True}
    )
    assert confirmed.json()["status"] == "confirmed"


def _student_login(client, pin: str = STUDENT_PASSWORD, username: str = STUDENT_USERNAME):
    return client.post("/v1/web/student/login", json={"username": username, "password": pin})


def _create_child(client, username: str, pin: str, age_band: str = "11-14"):
    return client.post(
        "/v1/students",
        json={"display_name": "Ali", "age_band": age_band, "username": username, "password": pin},
    )


def test_password_hash_round_trip():
    stored = hash_password("4821")
    assert verify_password("4821", stored)
    assert not verify_password("0000", stored)
    assert not verify_password("4821", "not-a-valid-hash")


def test_phone_numbers_are_normalized():
    assert normalize_phone("09121112233") == "09121112233"
    assert normalize_phone("+98 912 111 2233") == "09121112233"
    assert normalize_phone("0098-912-111-2233") == "09121112233"
    assert normalize_phone("۰۹۱۲۱۱۱۲۲۳۳") == "09121112233"
    assert normalize_phone("1234") is None
    assert normalize_phone("0812111223") is None


def test_public_pages_are_served(client):
    for path in ["/", "/student", "/parent"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


def test_adult_signs_in_with_sms_code(client):
    response = _adult_login(client)
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "parent"
    me = client.get("/v1/web/me?role=parent").json()
    assert me["role"] == "parent"
    assert "has_own_learning" in me


def test_first_visit_needs_a_name(client):
    phone = "09123334455"
    _clear_codes(phone)
    assert client.post("/v1/web/user/otp/request", json={"phone": phone}).status_code == 200
    code = _sms_code(phone)
    assert client.post("/v1/web/user/otp/verify", json={"phone": phone, "code": code}).status_code == 400
    # The name was missing, so the code was not used up and can still be entered with a name.
    assert client.post(
        "/v1/web/user/otp/verify", json={"phone": phone, "code": code, "full_name": "Nima"}
    ).status_code == 200


def test_resend_is_limited_to_once_a_minute(client):
    phone = "09124445566"
    _clear_codes(phone)
    assert client.post("/v1/web/user/otp/request", json={"phone": phone}).status_code == 200
    assert client.post("/v1/web/user/otp/request", json={"phone": phone}).status_code == 429


def test_wrong_codes_are_rejected_and_run_out_after_five_tries(client):
    phone = "09125556677"
    _clear_codes(phone)
    assert client.post("/v1/web/user/otp/request", json={"phone": phone}).status_code == 200
    real = _sms_code(phone)
    wrong = "999999" if real != "999999" else "000000"
    for _ in range(5):
        assert client.post(
            "/v1/web/user/otp/verify", json={"phone": phone, "code": wrong, "full_name": "Nima"}
        ).status_code == 401
    # Even the right code no longer works after five wrong tries. A new code is needed.
    assert client.post(
        "/v1/web/user/otp/verify", json={"phone": phone, "code": real, "full_name": "Nima"}
    ).status_code == 401


def test_bad_phone_number_is_refused(client):
    assert client.post("/v1/web/user/otp/request", json={"phone": "0812111223"}).status_code == 400
    assert client.post("/v1/web/user/otp/request", json={"phone": "12345"}).status_code == 422


def test_student_can_sign_in_with_username_and_pin(client):
    response = _student_login(client)
    assert response.status_code == 200
    assert response.json()["role"] == "student"
    assert client.get("/v1/web/me?role=student").json()["role"] == "student"


def test_wrong_pin_locks_the_child_login_for_a_while(client):
    adult = TestClient(app)
    _adult_login(adult)
    assert _create_child(adult, "pin-lock-child", "1357").status_code == 201

    child = TestClient(app)
    assert _student_login(child, "0000", "pin-lock-child").status_code == 401
    assert _student_login(child, "0000", "pin-lock-child").status_code == 401
    assert _student_login(child, "0000", "pin-lock-child").status_code == 401
    # Even the right PIN is refused during the lock.
    assert _student_login(child, "1357", "pin-lock-child").status_code == 429


def test_me_without_cookie_is_unauthorized(client):
    assert client.get("/v1/web/me?role=student").status_code == 401
    assert client.get("/v1/web/me?role=parent").status_code == 401


def test_adult_creates_child_who_signs_in_with_pin_and_starts_a_lesson(client):
    _adult_login(client)
    created = _create_child(client, NEW_CHILD_USERNAME, NEW_CHILD_PIN)
    assert created.status_code == 201, created.text
    student_id = created.json()["id"]
    assert client.post(f"/v1/students/{student_id}/consent", json={"accepted": True}).status_code == 201

    child = TestClient(app)
    assert _student_login(child, NEW_CHILD_PIN, NEW_CHILD_USERNAME).status_code == 200
    lesson = child.post(f"/v1/students/{student_id}/sessions", json={"duration_minutes": 5})
    assert lesson.status_code == 201, lesson.text


def test_adult_without_a_plan_cannot_create_a_child(client):
    fresh = TestClient(app)
    _adult_login(fresh, "09129990000", "No Plan Yet")
    response = _create_child(fresh, "no-plan-child", "1234")
    assert response.status_code == 402
    assert "plan" in response.json()["detail"].lower()


def test_failed_payment_does_not_activate_a_plan(client):
    adult = TestClient(app)
    _adult_login(adult, "09129991111", "Failed Payment")
    plans = adult.get("/v1/web/billing/plans").json()
    paid = adult.post("/v1/web/billing/checkout", json={"plan_id": plans[0]["id"]}).json()
    failed = adult.post("/v1/web/billing/fake/confirm", json={"payment_id": paid["payment_id"], "ok": False})
    assert failed.json()["status"] == "failed"
    assert adult.get("/v1/web/me?role=parent").json()["has_active_plan"] is False


def test_successful_payment_activates_the_plan_and_unlocks_children(client):
    adult = TestClient(app)
    _adult_login(adult, "09129992222", "Paid Parent")
    assert adult.get("/v1/web/me?role=parent").json()["has_active_plan"] is False
    _buy_plan(adult)
    assert adult.get("/v1/web/me?role=parent").json()["has_active_plan"] is True
    status = adult.get("/v1/web/billing/status").json()
    assert status["has_active_plan"] is True
    assert status["payments"][0]["status"] == "confirmed"
    assert _create_child(adult, "after-plan-child", "1234").status_code == 201


def test_payment_cannot_be_confirmed_by_another_adult(client):
    owner = TestClient(app)
    _adult_login(owner, "09129993333", "Owner")
    plans = owner.get("/v1/web/billing/plans").json()
    paid = owner.post("/v1/web/billing/checkout", json={"plan_id": plans[0]["id"]}).json()

    other = TestClient(app)
    _adult_login(other, "09129994444", "Someone Else")
    response = other.post("/v1/web/billing/fake/confirm", json={"payment_id": paid["payment_id"], "ok": True})
    assert response.status_code == 404


def test_dev_sms_outbox_shows_codes_only_in_development(client):
    response = client.get("/dev/sms-outbox")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_child_pin_must_be_four_to_six_digits(client):
    _adult_login(client)
    assert _create_child(client, "pin-format-child", "abcd").status_code == 400
    # Too short is refused by the request schema before the handler runs.
    assert _create_child(client, "pin-format-child", "12").status_code == 422


def test_adult_cannot_be_created_as_a_child(client):
    _adult_login(client)
    response = _create_child(client, "grown-up-child", "2468", age_band="adult")
    assert response.status_code == 403


def test_child_cannot_manage_students(client):
    child = TestClient(app)
    _student_login(child)
    response = child.post("/v1/students", json={"age_band": "11-14", "display_name": "x"})
    assert response.status_code == 403


def test_adult_cannot_see_another_familys_child(client):
    other = TestClient(app)
    assert _adult_login(other, OTHER_PARENT_PHONE, "Other Parent").status_code == 200

    student_id = _demo_student_id()
    assert other.get(f"/v1/students/{student_id}").status_code == 404
    listed = other.get("/v1/students").json()
    assert all(s["id"] != student_id for s in listed)


def test_adult_sees_their_child_in_the_list(client):
    _adult_login(client)
    listed = client.get("/v1/students").json()
    assert any(s["username"] == STUDENT_USERNAME for s in listed)


def test_adult_usage_and_report_are_structured_without_raw_codes(client):
    _adult_login(client)
    student_id = _demo_student_id()
    usage = client.get(f"/v1/students/{student_id}/usage")
    assert usage.status_code == 200
    assert {"lessons_completed", "minutes_used", "last_lesson_at", "plan_end_date"} <= usage.json().keys()
    report = client.get(f"/v1/students/{student_id}/reports/parent")
    assert report.status_code == 200
    assert report.json()["summary_fa"]


def test_adult_can_learn_for_themself_and_guardian_cannot_see_it(client):
    adult = TestClient(app)
    assert _adult_login(adult, "09126667788", "Self Learner").status_code == 200
    _buy_plan(adult)
    started = adult.post("/v1/web/user/self")
    assert started.status_code == 200, started.text
    self_id = started.json()["id"]
    assert adult.get("/v1/web/me?role=parent").json()["has_own_learning"] is True

    # The learner's own view works through the learner cookie.
    own = adult.get(f"/v1/students/{self_id}/usage", headers={"X-Zaban-Role": "student"})
    assert own.status_code == 200
    # The same person as an adult sees the learner profile as not theirs to manage.
    assert adult.get(f"/v1/students/{self_id}/usage", headers={"X-Zaban-Role": "parent"}).status_code == 404
    listed = adult.get("/v1/students", headers={"X-Zaban-Role": "parent"}).json()
    assert all(s["id"] != self_id for s in listed)


def test_self_learning_profile_is_created_once(client):
    adult = TestClient(app)
    _adult_login(adult, "09127778899", "Repeat Learner")
    _buy_plan(adult)
    first = adult.post("/v1/web/user/self").json()["id"]
    second = adult.post("/v1/web/user/self").json()["id"]
    assert first == second


def test_logout_everywhere_ends_adult_and_learner_sessions(client):
    adult = TestClient(app)
    _adult_login(adult, "09128889900", "Logout Everywhere")
    _buy_plan(adult)
    adult.post("/v1/web/user/self")
    assert adult.get("/v1/web/me?role=student").status_code == 200

    assert adult.post("/v1/web/user/logout-all").status_code == 200
    assert adult.get("/v1/web/me?role=parent").status_code == 401
    assert adult.get("/v1/web/me?role=student").status_code == 401


def test_pin_reset_ends_the_childs_sessions(client):
    adult = TestClient(app)
    _adult_login(adult)
    created = _create_child(adult, "reset-pin-child", "1111")
    student_id = created.json()["id"]

    child = TestClient(app)
    assert _student_login(child, "1111", "reset-pin-child").status_code == 200
    assert adult.post(f"/v1/students/{student_id}/password", json={"password": "2222"}).status_code == 200
    assert child.get("/v1/web/me?role=student").status_code == 401
    assert _student_login(TestClient(app), "2222", "reset-pin-child").status_code == 200


def test_logout_clears_access(client):
    _student_login(client)
    client.post("/v1/web/logout?role=student")
    assert client.get("/v1/web/me?role=student").status_code == 401


def test_adult_and_child_can_be_signed_in_together(client):
    _student_login(client)
    _adult_login(client)
    assert client.get("/v1/web/me?role=student").json()["role"] == "student"
    assert client.get("/v1/web/me?role=parent").json()["role"] == "parent"
    assert client.get("/v1/students", headers={"X-Zaban-Role": "parent"}).status_code == 200
    assert client.get("/v1/students", headers={"X-Zaban-Role": "student"}).status_code == 403
