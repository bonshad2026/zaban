import os
import secrets

from fastapi.testclient import TestClient

from zaban.db import SessionLocal
from zaban.main import app
from zaban.models import LearnerDetails, OtpCode, Student
from zaban.services.otp import normalize_phone
from zaban.services.passwords import hash_password, verify_password
from zaban.services.sms import dev_outbox

# Values come from conftest.py, which generates them for each test run.
PARENT_PHONE = os.environ["ZABAN_DEMO_PARENT_PHONE"]
PARENT_PASSWORD = os.environ["ZABAN_DEMO_PARENT_PASSWORD"]
ADULT_PASSWORD = "test-adult-pass-123"
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


def _sign_up(client, phone: str, name: str = "Test Adult", password: str = ADULT_PASSWORD):
    # Clears old codes so the 60-second resend limit does not get in the way of each test.
    _clear_codes(phone)
    assert client.post("/v1/web/user/otp/request", json={"phone": phone, "purpose": "signup"}).status_code == 200
    return client.post(
        "/v1/web/user/signup",
        json={
            "phone": phone,
            "code": _sms_code(phone),
            "full_name": name,
            "password": password,
            "age_confirmed": True,
        },
    )


def _adult_login(client, phone: str = PARENT_PHONE, name: str = "Test Adult"):
    # Signs in when the account exists, otherwise creates it through sign-up.
    password = PARENT_PASSWORD if phone == PARENT_PHONE else ADULT_PASSWORD
    response = client.post("/v1/web/user/login", json={"phone": phone, "password": password})
    if response.status_code == 200:
        return response
    return _sign_up(client, phone, name, password)


def _buy_plan(client) -> None:
    # Uses the development gateway: checkout, the fake "pay" button, then the administrator confirms the payment.
    plans = client.get("/v1/web/billing/plans").json()
    paid = client.post("/v1/web/billing/checkout", json={"plan_id": plans[0]["id"]})
    assert paid.status_code == 201, paid.text
    payment_id = paid.json()["payment_id"]
    marked = client.post("/v1/web/billing/fake/confirm", json={"payment_id": payment_id, "ok": True})
    assert marked.json()["status"] == "confirmed"

    admin = TestClient(app)
    assert admin.post("/v1/admin/api/login", json={"password": os.environ["ADMIN_PASSWORD"]}).status_code == 200
    decided = admin.post(f"/v1/admin/api/payments/{payment_id}/decision", json={"ok": True})
    assert decided.json()["status"] == "confirmed"


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


def test_adult_signs_up_then_signs_in_with_password(client):
    phone = "09121230001"
    response = _sign_up(client, phone, "Sara")
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "parent"
    assert client.get("/v1/web/me?role=parent").json()["role"] == "parent"

    fresh = TestClient(app)
    assert fresh.post("/v1/web/user/login", json={"phone": phone, "password": ADULT_PASSWORD}).status_code == 200
    assert fresh.post("/v1/web/user/login", json={"phone": phone, "password": "wrong-pass-999"}).status_code == 401


def test_signup_needs_age_confirmation_and_a_free_number(client):
    phone = "09121230002"
    _clear_codes(phone)
    assert client.post("/v1/web/user/otp/request", json={"phone": phone, "purpose": "signup"}).status_code == 200
    response = client.post(
        "/v1/web/user/signup",
        json={"phone": phone, "code": _sms_code(phone), "full_name": "Nima", "password": ADULT_PASSWORD, "age_confirmed": False},
    )
    assert response.status_code == 400
    # The code was not used up, so the same code still works once the age is confirmed.
    assert _sign_up(client, phone, "Nima").status_code == 201
    assert client.post("/v1/web/user/otp/request", json={"phone": phone, "purpose": "signup"}).status_code == 409


def test_resend_is_limited_to_once_a_minute(client):
    phone = "09124445566"
    _clear_codes(phone)
    assert client.post("/v1/web/user/otp/request", json={"phone": phone}).status_code == 200
    assert client.post("/v1/web/user/otp/request", json={"phone": phone}).status_code == 429


def test_wrong_codes_are_rejected_and_run_out_after_five_tries(client):
    phone = "09125556677"
    _clear_codes(phone)
    assert client.post("/v1/web/user/otp/request", json={"phone": phone, "purpose": "signup"}).status_code == 200
    real = _sms_code(phone)
    wrong = "999999" if real != "999999" else "000000"
    body = {"phone": phone, "full_name": "Nima", "password": ADULT_PASSWORD, "age_confirmed": True}
    for _ in range(5):
        assert client.post("/v1/web/user/signup", json={**body, "code": wrong}).status_code == 401
    # Even the right code no longer works after five wrong tries. A new code is needed.
    assert client.post("/v1/web/user/signup", json={**body, "code": real}).status_code == 401


def test_wrong_password_locks_the_adult_login_for_a_while(client):
    phone = "09121230003"
    _sign_up(client, phone, "Lock Test")
    locked = TestClient(app)
    for _ in range(5):
        assert locked.post("/v1/web/user/login", json={"phone": phone, "password": "nope-nope-1"}).status_code == 401
    assert locked.post("/v1/web/user/login", json={"phone": phone, "password": ADULT_PASSWORD}).status_code == 429


def test_forgotten_password_is_reset_with_a_code_and_older_sign_ins_end(client):
    phone = "09121230004"
    _sign_up(client, phone, "Reset Me")
    old = TestClient(app)
    assert old.post("/v1/web/user/login", json={"phone": phone, "password": ADULT_PASSWORD}).status_code == 200

    _clear_codes(phone)
    assert client.post("/v1/web/user/otp/request", json={"phone": phone, "purpose": "reset"}).status_code == 200
    code = _sms_code(phone)
    new_password = "brand-new-pass-456"
    reset = client.post("/v1/web/user/password/reset", json={"phone": phone, "code": code, "password": new_password})
    assert reset.status_code == 200, reset.text
    assert old.get("/v1/web/me?role=parent").status_code == 401
    assert TestClient(app).post("/v1/web/user/login", json={"phone": phone, "password": new_password}).status_code == 200


def test_development_returns_the_code_so_sign_up_can_be_tried_without_sms(client):
    phone = "09121230005"
    _clear_codes(phone)
    sent = client.post("/v1/web/user/otp/request", json={"phone": phone, "purpose": "signup"}).json()
    assert sent["dev_code"] == _sms_code(phone)
    created = client.post(
        "/v1/web/user/signup",
        json={"phone": phone, "code": sent["dev_code"], "full_name": "No SMS", "password": ADULT_PASSWORD, "age_confirmed": True},
    )
    assert created.status_code == 201


def test_reset_for_an_unknown_number_gives_the_same_answer(client):
    # The form must not reveal which numbers have accounts.
    response = client.post("/v1/web/user/otp/request", json={"phone": "09129998877", "purpose": "reset"})
    assert response.status_code == 200
    assert not [number for number, _ in dev_outbox() if number == "09129998877"]


def test_bad_phone_number_is_refused(client):
    assert client.post("/v1/web/user/otp/request", json={"phone": "0812111223"}).status_code == 400
    assert client.post("/v1/web/user/otp/request", json={"phone": "12345"}).status_code == 422


def test_me_without_cookie_is_unauthorized(client):
    assert client.get("/v1/web/me?role=student").status_code == 401
    assert client.get("/v1/web/me?role=parent").status_code == 401


def test_adult_without_a_plan_cannot_start_learning(client):
    fresh = TestClient(app)
    _adult_login(fresh, "09129990000", "No Plan Yet")
    response = fresh.post("/v1/web/user/self")
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


def test_successful_payment_activates_the_plan_and_unlocks_learning(client):
    adult = TestClient(app)
    _adult_login(adult, "09129992222", "Paid Parent")
    assert adult.get("/v1/web/me?role=parent").json()["has_active_plan"] is False
    _buy_plan(adult)
    assert adult.get("/v1/web/me?role=parent").json()["has_active_plan"] is True
    status = adult.get("/v1/web/billing/status").json()
    assert status["has_active_plan"] is True
    assert status["payments"][0]["status"] == "confirmed"
    assert adult.post("/v1/web/user/self").status_code == 200


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


def test_adult_cannot_be_created_as_a_child(client):
    _adult_login(client)
    response = _create_child(client, "grown-up-child", "2468", age_band="adult")
    assert response.status_code == 403


def test_adult_can_learn_for_themself_and_guardian_cannot_see_it(client):
    adult = TestClient(app)
    assert _adult_login(adult, "09126667788", "Self Learner").status_code in (200, 201)
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
    # Adults no longer manage students here. Only tenant API keys do.
    assert adult.get("/v1/students", headers={"X-Zaban-Role": "parent"}).status_code == 403


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


def test_logout_clears_access(client):
    _student_login(client)
    client.post("/v1/web/logout?role=student")
    assert client.get("/v1/web/me?role=student").status_code == 401


def _complete_profile(student_id: str) -> None:
    # A lesson needs a level, an age and a gender. Tests set them directly, as the parent or learner would.
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        student.cefr_level = student.cefr_level or "A2"
        db.merge(LearnerDetails(student_id=student_id, age=11, gender="female"))
        db.commit()
