from datetime import timedelta

from helpers_learner import learner_login, self_student

from zaban.db import SessionLocal
from zaban.models import LessonTopic, Student, TutorSession, utcnow
from zaban.services.curriculum import DEFAULT_LEVEL, band_code, path_topics, variant_for


def test_repeating_a_finished_lesson_averages_its_attempts_and_keeps_the_place(client):
    learner_login(client)
    with SessionLocal() as db:
        student = self_student(db)
        band = band_code(student.age_band)
        level = student.cefr_level or DEFAULT_LEVEL
        path = path_topics(db, student)
        assert len(path) >= 2
        first, second = path[0], path[1]
        now = utcnow()
        made = []
        # Two attempts at the first lesson: 60 and 100 points, 10 and 8 minutes long.
        for score, started_ago, minutes in [(60.0, 40, 10), (100.0, 20, 8)]:
            session = TutorSession(
                student_id=student.id,
                duration_minutes=10,
                status="completed",
                started_at=now - timedelta(minutes=started_ago),
                ends_at=now,
                ended_at=now - timedelta(minutes=started_ago - minutes),
                score=score,
                evaluation="Good work.",
            )
            db.add(session)
            db.flush()
            variant = variant_for(db, first.id, band, level)
            db.add(LessonTopic(session_id=session.id, topic_id=first.id, variant_id=variant.id, catalog_version=1))
            made.append(session.id)
        student.repeat_topic_id = None
        db.commit()
        student_id = student.id

    try:
        body = client.get("/v1/web/student/progress").json()
        lessons = body["lessons"]
        assert lessons[0]["status"] == "done"
        assert lessons[0]["visits"] == 2
        assert lessons[0]["average"] == 80.0
        assert lessons[0]["average_minutes"] == 9.0
        assert len(lessons[0]["attempts"]) == 2
        assert lessons[1]["status"] == "current"
        assert body["current"] == 2
        # The overall percent counts the finished lesson's average score, the others count zero.
        assert body["percent"] == round(80.0 / body["total"], 1)

        # Repeating the finished lesson changes its place in the repeat queue, not the current step.
        assert client.post("/v1/web/student/progress/repeat", json={"item_id": first.id}).status_code == 200
        again = client.get("/v1/web/student/progress").json()
        assert again["lessons"][0]["repeat"] is True
        assert again["current"] == 2
    finally:
        with SessionLocal() as db:
            db.query(LessonTopic).filter(LessonTopic.session_id.in_(made)).delete(synchronize_session=False)
            db.query(TutorSession).filter(TutorSession.id.in_(made)).delete(synchronize_session=False)
            db.get(Student, student_id).repeat_topic_id = None
            db.commit()
