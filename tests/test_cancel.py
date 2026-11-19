from datetime import timedelta

from helpers_learner import demo_student, learner_login
from zaban.db import SessionLocal
from zaban.models import SelfTest, TutorSession, utcnow


def test_a_cancelled_lesson_and_test_leave_the_active_slot_the_list_and_the_reports(client):
    learner_login(client)
    student = demo_student()
    now = utcnow()
    with SessionLocal() as db:
        session = TutorSession(
            student_id=student.id, duration_minutes=10, status="active", started_at=now,
            ends_at=now + timedelta(minutes=10), session_kind="lesson",
        )
        test = SelfTest(
            student_id=student.id, kind="qa", skill="listening", minutes=10, status="active",
            ends_at=now + timedelta(minutes=10),
        )
        db.add_all([session, test])
        db.commit()
        session_id, test_id = session.id, test.id
    try:
        assert client.post(f"/v1/sessions/{session_id}/cancel").status_code == 200
        assert client.post(f"/v1/web/student/self-tests/{test_id}/cancel").status_code == 200
        # A closed lesson cannot be cancelled a second time.
        assert client.post(f"/v1/sessions/{session_id}/cancel").status_code == 409

        active = client.get(f"/v1/students/{student.id}/sessions/active").json()
        assert not active.get("session") or active["session"].get("id") != session_id

        items = client.get(f"/v1/students/{student.id}/reports/items").json()["items"]
        assert all(item["id"] not in (session_id, test_id) for item in items)

        tests = client.get("/v1/web/student/self-tests").json()
        assert all(row["id"] != test_id for row in tests)
    finally:
        with SessionLocal() as db:
            db.query(TutorSession).filter(TutorSession.id == session_id).delete()
            db.query(SelfTest).filter(SelfTest.id == test_id).delete()
            db.commit()
