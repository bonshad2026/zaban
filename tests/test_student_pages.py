import os
from datetime import timedelta

from zaban.db import SessionLocal
from zaban.models import BillingPlan, LessonItem, LearningProgram, Payment, ProgramItem, Student, TutorSession, utcnow
from zaban.reports import _session_rows
from helpers_learner import learner_login, self_student





def test_report_rows_title_program_lessons_and_free_talks(client):
    # A lesson of the program is titled with its program item, and a free talk gets a plain title.
    with SessionLocal() as db:
        student = self_student(db)
        program = db.query(LearningProgram).order_by(LearningProgram.id).first()
        item = db.query(ProgramItem).filter(ProgramItem.program_id == program.id).order_by(ProgramItem.position).first()
        now = utcnow()
        lesson = TutorSession(student_id=student.id, duration_minutes=10, status="completed", started_at=now,
                              ends_at=now + timedelta(minutes=10))
        free = TutorSession(student_id=student.id, duration_minutes=5, status="completed", started_at=now,
                            ends_at=now + timedelta(minutes=5))
        db.add_all([lesson, free])
        db.flush()
        db.add(LessonItem(session_id=lesson.id, program_id=program.id, position=item.position,
                          program_version=program.version, counted=True))
        db.commit()
        try:
            rows = {row["id"]: row for row in _session_rows(db, student)}
            assert rows[lesson.id]["lesson_number"] == item.position + 1
            assert rows[lesson.id]["lesson_title"] == item.title
            assert rows[free.id]["lesson_number"] is None
        finally:
            db.query(LessonItem).filter(LessonItem.session_id.in_([lesson.id, free.id])).delete(synchronize_session=False)
            db.query(TutorSession).filter(TutorSession.id.in_([lesson.id, free.id])).delete(synchronize_session=False)
            db.commit()


def test_student_payments_show_the_plan_name(client):
    learner_login(client)
    with SessionLocal() as db:
        student = self_student(db)
        owner = student.guardian_id or student.self_owner_id
        plan = db.query(BillingPlan).order_by(BillingPlan.price_toman).first()
        payment = Payment(guardian_id=owner, plan_id=plan.id, amount_toman=plan.price_toman, status="confirmed",
                          gateway="fake", created_at=utcnow())
        db.add(payment)
        db.commit()
        payment_id = payment.id
        plan_name = plan.name
        try:
            rows = client.get("/v1/web/student/payments").json()
            row = next(r for r in rows if r["id"] == payment_id)
            assert row["plan_name"] == plan_name
            assert row["amount_toman"] == plan.price_toman
        finally:
            db.query(Payment).filter(Payment.id == payment_id).delete()
            db.commit()


def test_score_line_is_read_and_removed_from_the_evaluation():
    from zaban.services.self_test import split_score

    text, score = split_score("Strengths: clear answers.\nNext steps: practise questions.\nSCORE: 85")
    assert score == 85.0
    assert "SCORE" not in text
    assert text.startswith("Strengths: clear answers.")


def test_missing_or_large_score_is_handled():
    from zaban.services.self_test import split_score

    assert split_score("A short evaluation without a score.") == ("A short evaluation without a score.", None)
    assert split_score("Good.\nSCORE: 150")[1] == 100.0


def test_program_lessons_have_english_titles(client):
    from zaban.services.programs import seed_programs

    with SessionLocal() as db:
        seed_programs(db)
        first = db.query(ProgramItem).filter(ProgramItem.program_id == "T-A1-daily-p1", ProgramItem.position == 0).one()
        assert first.title == "سلام و معرفی"
        assert first.title_en == "Hello and introductions"

