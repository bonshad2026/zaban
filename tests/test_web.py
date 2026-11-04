import os
import secrets

from fastapi.testclient import TestClient

from zaban.db import SessionLocal
from zaban.main import app
from zaban.models import Guardian, Student, Tenant
from zaban.services.passwords import hash_password, verify_password

# Values come from conftest.py, which generates them for each test run.
PARENT_EMAIL = os.environ["ZABAN_DEMO_PARENT_EMAIL"]
PARENT_PASSWORD = os.environ["ZABAN_DEMO_PARENT_PASSWORD"]
STUDENT_USERNAME = os.environ["ZABAN_DEMO_STUDENT_USERNAME"]
STUDENT_PASSWORD = os.environ["ZABAN_DEMO_STUDENT_PASSWORD"]
OTHER_PARENT_EMAIL = "other.parent@example.com"
OTHER_PARENT_PASSWORD = secrets.token_urlsafe(12)
NEW_CHILD_USERNAME = "web-test-child"
NEW_CHILD_PASSWORD = secrets.token_urlsafe(12)


def _demo_student_id() -> str:
    with SessionLocal() as db:
        return db.query(Student).filter(Student.username == STUDENT_USERNAME).one().id


def _add_guardian(email: str, password: str) -> None:
    with SessionLocal() as db:
        tenant = db.query(Tenant).filter(Tenant.name == "Demo Tenant").one()
        db.add(
            Guardian(
                tenant_id=tenant.id,
                email=email,
                full_name="Other Parent",
                password_hash=hash_password(password),
            )
        )
        db.commit()


def _student_login(client) -> None:
    client.post("/v1/web/student/login", json={"username": STUDENT_USERNAME, "password": STUDENT_PASSWORD})


def _parent_login(client) -> None:
    client.post("/v1/web/parent/login", json={"email": PARENT_EMAIL, "password": PARENT_PASSWORD})


def test_password_hash_round_trip():
    stored = hash_password("secret123")
    assert verify_password("secret123", stored)
    assert not verify_password("wrong-one", stored)
    assert not verify_password("secret123", "not-a-valid-hash")


def test_public_pages_are_served(client):
    for path in ["/", "/student", "/parent"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


def test_student_can_sign_in_and_see_own_identity(client):
    response = client.post("/v1/web/student/login", json={"username": STUDENT_USERNAME, "password": STUDENT_PASSWORD})
    assert response.status_code == 200
    assert response.json()["role"] == "student"
    me = client.get("/v1/web/me?role=student")
    assert me.status_code == 200
    assert me.json()["role"] == "student"


def test_wrong_password_is_rejected(client):
    response = client.post("/v1/web/student/login", json={"username": STUDENT_USERNAME, "password": "not-the-password"})
    assert response.status_code == 401


def test_me_without_cookie_is_unauthorized(client):
    assert client.get("/v1/web/me?role=student").status_code == 401


def test_parent_creates_child_who_can_sign_in_and_start_a_lesson(client):
    _parent_login(client)
    created = client.post(
        "/v1/students",
        json={
            "display_name": "Ali",
            "age_band": "11-14",
            "username": NEW_CHILD_USERNAME,
            "password": NEW_CHILD_PASSWORD,
        },
    )
    assert created.status_code == 201, created.text
    student_id = created.json()["id"]
    assert client.post(f"/v1/students/{student_id}/consent", json={"accepted": True}).status_code == 201

    child = TestClient(app)
    assert child.post(
        "/v1/web/student/login", json={"username": NEW_CHILD_USERNAME, "password": NEW_CHILD_PASSWORD}
    ).status_code == 200
    lesson = child.post(f"/v1/students/{student_id}/sessions", json={"duration_minutes": 5})
    assert lesson.status_code == 201, lesson.text


def test_child_cannot_manage_students(client):
    child = TestClient(app)
    _student_login(child)
    response = child.post("/v1/students", json={"age_band": "adult", "display_name": "x"})
    assert response.status_code == 403


def test_parent_cannot_see_another_familys_child(client):
    _add_guardian(OTHER_PARENT_EMAIL, OTHER_PARENT_PASSWORD)
    other = TestClient(app)
    assert other.post(
        "/v1/web/parent/login", json={"email": OTHER_PARENT_EMAIL, "password": OTHER_PARENT_PASSWORD}
    ).status_code == 200

    student_id = _demo_student_id()
    assert other.get(f"/v1/students/{student_id}").status_code == 404
    listed = other.get("/v1/students").json()
    assert all(s["id"] != student_id for s in listed)


def test_parent_sees_their_child_in_the_list(client):
    _parent_login(client)
    listed = client.get("/v1/students").json()
    assert any(s["username"] == STUDENT_USERNAME for s in listed)


def test_parent_usage_and_report_are_structured_without_raw_codes(client):
    _parent_login(client)
    student_id = _demo_student_id()
    usage = client.get(f"/v1/students/{student_id}/usage")
    assert usage.status_code == 200
    assert {"lessons_completed", "minutes_used", "last_lesson_at", "plan_end_date"} <= usage.json().keys()
    report = client.get(f"/v1/students/{student_id}/reports/parent")
    assert report.status_code == 200
    assert report.json()["summary_fa"]


def test_logout_clears_access(client):
    _student_login(client)
    client.post("/v1/web/logout?role=student")
    assert client.get("/v1/web/me?role=student").status_code == 401


def test_parent_and_child_can_be_signed_in_together(client):
    _student_login(client)
    _parent_login(client)
    assert client.get("/v1/web/me?role=student").json()["role"] == "student"
    assert client.get("/v1/web/me?role=parent").json()["role"] == "parent"
    assert client.get("/v1/students", headers={"X-Zaban-Role": "parent"}).status_code == 200
    assert client.get("/v1/students", headers={"X-Zaban-Role": "student"}).status_code == 403
