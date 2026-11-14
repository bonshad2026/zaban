import os
from datetime import timedelta

from zaban.db import SessionLocal
from zaban.models import BillingPlan, Payment, Student, TutorSession, utcnow
from helpers_learner import learner_login, self_student





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


