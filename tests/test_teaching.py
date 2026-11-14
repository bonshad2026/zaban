from fastapi.testclient import TestClient

from zaban.db import SessionLocal
from zaban.main import app
from zaban.models import OtpCode
from zaban.services.sms import dev_outbox


def _adult(phone: str, name: str) -> TestClient:
    # Clears older codes so the per-IP sign-up limit does not get in the way of the test.
    with SessionLocal() as db:
        db.query(OtpCode).delete()
        db.commit()
    adult = TestClient(app)
    assert adult.post("/v1/web/user/otp/request", json={"phone": phone, "purpose": "signup"}).status_code == 200
    code = [c for n, c in dev_outbox() if n == phone][-1]
    created = adult.post(
        "/v1/web/user/signup",
        json={"phone": phone, "code": code, "full_name": name, "password": "teach-pass-1"},
    )
    assert created.status_code == 201, created.text
    return adult


def _code(adult: TestClient) -> str:
    return adult.get("/v1/web/user/referrals").json()["code"]


def test_learner_chooses_a_teacher_by_code_and_the_teacher_sees_only_that_learner(client):
    teacher = _adult("09121230501", "Sara Teacher")
    learner = _adult("09121230502", "Ali Learner")
    other = _adult("09121230503", "Nima Other")
    teacher_code = _code(teacher)

    # The learner checks the code first and sees the teacher's name.
    shown = learner.post("/v1/web/user/teacher/lookup", json={"code": teacher_code.lower()})
    assert shown.status_code == 200, shown.text
    assert shown.json()["teacher"]["name"] == "Sara Teacher"
    assert learner.post("/v1/web/user/teacher/lookup", json={"code": _code(learner)}).status_code == 400
    assert learner.post("/v1/web/user/teacher/lookup", json={"code": "ZZZZZZ"}).status_code == 400

    # Choosing needs the tick. Without it nothing changes.
    assert learner.put("/v1/web/user/teacher", json={"code": teacher_code}).status_code == 400
    chosen = learner.put("/v1/web/user/teacher", json={"code": teacher_code, "confirm": True})
    assert chosen.status_code == 200, chosen.text
    assert learner.get("/v1/web/user/teacher").json()["teacher"]["name"] == "Sara Teacher"

    students = teacher.get("/v1/web/user/students").json()
    assert [s["name"] for s in students] == ["Ali Learner"]
    assert teacher.get("/v1/web/me?role=parent").json()["students"] == 1

    # The teacher can open this learner's progress and report, and nobody else can.
    learner_id = students[0]["id"]
    assert teacher.get(f"/v1/web/user/students/{learner_id}/progress").status_code == 200
    assert teacher.get(f"/v1/web/user/students/{learner_id}/report").status_code == 200
    assert other.get(f"/v1/web/user/students/{learner_id}/progress").status_code == 404
    assert learner.get(f"/v1/web/user/students/{learner_id}/progress").status_code == 404

    # Removing the teacher ends the access at once.
    assert learner.delete("/v1/web/user/teacher").json()["teacher"] is None
    assert teacher.get("/v1/web/user/students").json() == []
    assert teacher.get(f"/v1/web/user/students/{learner_id}/progress").status_code == 404
