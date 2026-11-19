from datetime import timedelta

from helpers_learner import demo_student, learner_login
from zaban.db import SessionLocal
from zaban.models import TutorSession, utcnow
from zaban.services.free_topics import TOPICS, suggest_topic
from zaban.models import Student


def test_the_suggestion_avoids_the_topics_of_recent_free_talks(client):
    learner_login(client)
    student = demo_student()
    now = utcnow()
    kept = TOPICS[-1]
    used = [topic for topic in TOPICS if topic != kept]
    rows = []
    with SessionLocal() as db:
        for index, topic in enumerate(used):
            row = TutorSession(
                student_id=student.id, duration_minutes=0, status="completed", started_at=now + timedelta(seconds=index),
                ends_at=now, session_kind="free", topic=topic,
            )
            db.add(row)
            rows.append(row)
        db.commit()
        row_ids = [row.id for row in rows]
        try:
            # The learner has talked about every topic but one, so that one is suggested.
            assert suggest_topic(db, db.get(Student, student.id)) == kept
            suggestion = client.get("/v1/web/student/free-topic").json()["suggestion"]
            assert suggestion in TOPICS
        finally:
            db.query(TutorSession).filter(TutorSession.id.in_(row_ids)).delete(synchronize_session=False)
            db.commit()


def test_a_free_talk_without_a_time_limit_sends_no_countdown(client):
    learner_login(client)
    student = demo_student()
    now = utcnow()
    with SessionLocal() as db:
        row = TutorSession(
            student_id=student.id, duration_minutes=0, status="active", started_at=now,
            ends_at=now + timedelta(hours=24), session_kind="free",
        )
        db.add(row)
        db.commit()
        row_id = row.id
    try:
        active = client.get(f"/v1/students/{student.id}/sessions/active").json()
        assert active["session"]["id"] == row_id
        assert active["session"]["seconds_left"] is None
    finally:
        with SessionLocal() as db:
            db.query(TutorSession).filter(TutorSession.id == row_id).delete()
            db.commit()
