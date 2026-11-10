import uuid

from zaban.db import SessionLocal
from zaban.models import LessonItem, ProgramItem, Student, StudentProgress, Tenant, TutorSession, utcnow
from zaban.services.programs import advance_if_done, current_item, item_stats, ordered_items, reorder_items

PROGRAM_ID = "T-A1-daily-p1"


def _new_student() -> str:
    with SessionLocal() as db:
        tenant = db.query(Tenant).first()
        student = Student(tenant_id=tenant.id, external_user_id=f"order-{uuid.uuid4().hex}", display_name="Order test",
                          age_band="T", cefr_level="A1")
        db.add(student)
        db.flush()
        db.add(StudentProgress(student_id=student.id, program_id=PROGRAM_ID, position=0, status="active"))
        db.commit()
        return student.id


def _play(student_id: str, item: ProgramItem, score=None) -> None:
    # A lesson that was played and ended on this item, then counted as the program does.
    with SessionLocal() as db:
        now = utcnow()
        session = TutorSession(student_id=student_id, duration_minutes=10, status="completed", started_at=now,
                               ends_at=now, ended_at=now, score=score)
        db.add(session)
        db.flush()
        db.add(LessonItem(session_id=session.id, program_id=PROGRAM_ID, position=item.position, item_id=item.id, program_version=1))
        db.commit()
        advance_if_done(db, student_id)
        db.commit()


def _items() -> list[ProgramItem]:
    with SessionLocal() as db:
        return [ProgramItem(id=i.id, position=i.position, program_id=i.program_id, title=i.title) for i in ordered_items(db, PROGRAM_ID)]


def _original_order() -> list[int]:
    return [i.id for i in _items()]


def test_after_reordering_the_next_lesson_is_the_first_unfinished_topic(client):
    original = _original_order()
    student_id = _new_student()
    try:
        items = _items()
        _play(student_id, items[0])
        # Move the third topic to the front. The first topic is already done, so the next lesson is the third one.
        new_order = [original[2], original[0], original[1]] + original[3:]
        with SessionLocal() as db:
            reorder_items(db, PROGRAM_ID, new_order)
            db.commit()
            progress = db.get(StudentProgress, student_id)
            advance_if_done(db, student_id)
            db.commit()
            progress = db.get(StudentProgress, student_id)
            assert progress.position == 0
            assert current_item(db, progress).id == original[2]
    finally:
        with SessionLocal() as db:
            reorder_items(db, PROGRAM_ID, original)
            db.commit()


def test_a_repeated_topic_does_not_move_the_place_in_the_program(client):
    student_id = _new_student()
    items = _items()
    _play(student_id, items[0])
    with SessionLocal() as db:
        progress = db.get(StudentProgress, student_id)
        progress.revisit_item_id = items[0].id
        db.commit()
        assert current_item(db, progress).id == items[0].id
    _play(student_id, items[0])
    with SessionLocal() as db:
        progress = db.get(StudentProgress, student_id)
        assert progress.position == 1
        assert progress.revisit_item_id is None


def test_the_average_is_taken_over_every_lesson_of_a_topic(client):
    student_id = _new_student()
    items = _items()
    _play(student_id, items[0], score=20)
    _play(student_id, items[0], score=70)
    with SessionLocal() as db:
        stats = {row["item_id"]: row for row in item_stats(db, student_id, PROGRAM_ID)}
        assert stats[items[0].id]["visits"] == 2
        assert stats[items[0].id]["average"] == 45.0
        assert stats[items[0].id]["done"] is True
        assert stats[items[1].id]["visits"] == 0 and stats[items[1].id]["average"] is None
