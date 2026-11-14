import uuid
from datetime import timedelta

from zaban.curriculum_data import BAND_CODES
from zaban.db import SessionLocal
from zaban.models import LessonTopic, Student, Tenant, TutorSession, utcnow
from zaban.services.curriculum import choose_topic, ordered_topics, path_topics, set_topic_order


def _student(db, level: str = "A2") -> Student:
    tenant = db.query(Tenant).first()
    student = Student(
        tenant_id=tenant.id,
        external_user_id=f"path-{uuid.uuid4().hex}",
        display_name="Path learner",
        age_band="11-14",
        cefr_level=level,
        created_at=utcnow(),
    )
    db.add(student)
    db.commit()
    return student


def _finish_topic(db, student: Student, topic_id: str, variant_id: str) -> None:
    now = utcnow()
    session = TutorSession(
        student_id=student.id,
        duration_minutes=10,
        status="completed",
        started_at=now,
        ends_at=now + timedelta(minutes=10),
        ended_at=now,
    )
    db.add(session)
    db.flush()
    db.add(LessonTopic(session_id=session.id, topic_id=topic_id, variant_id=variant_id, catalog_version=1))
    db.commit()


def test_topics_have_a_saved_order_from_startup(client):
    with SessionLocal() as db:
        positions = [t.position for t in ordered_topics(db)]
        assert positions and all(p >= 1 for p in positions)
        assert positions == sorted(positions)


def test_next_lesson_is_the_first_topic_not_yet_covered_and_order_changes_it(client):
    with SessionLocal() as db:
        student = _student(db)
        path = path_topics(db, student)
        original_order = [t.id for t in ordered_topics(db)]
        assert len(path) >= 2
        first = choose_topic(db, student)
        assert first is not None and first[0].id == path[0].id

        # A finished topic is skipped, so the lesson moves on to the next one in the path.
        _finish_topic(db, student, path[0].id, first[1].id)
        after = choose_topic(db, student)
        assert after is not None and after[0].id == path[1].id

        # Dragging the next topic to the front makes it the next lesson; the finished topic stays skipped.
        new_order = [path[1].id, path[0].id] + [t.id for t in ordered_topics(db) if t.id not in (path[0].id, path[1].id)]
        set_topic_order(db, new_order)
        moved = choose_topic(db, student)
        assert moved is not None and moved[0].id == path[1].id
        # Restore the order the other tests expect.
        set_topic_order(db, original_order)
