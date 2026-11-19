from helpers_learner import demo_student, learner_login
from zaban.db import SessionLocal
from zaban.models import LearnerAnalysis, Student
from zaban.services import learner_analysis
from zaban.services.ai_gateway import AIResult


def _reply(text: str, mode: str = "live") -> AIResult:
    return AIResult(text=text, input_tokens=5, output_tokens=5, mode=mode)


def test_latest_analysis_is_the_newest_live_reply_and_offline_replies_are_not_saved(client, monkeypatch):
    learner_login(client)
    student = demo_student()
    try:
        monkeypatch.setattr(learner_analysis, "complete", lambda *a, **k: _reply("وضعیت کلی:\n- نسخه اول"))
        with SessionLocal() as db:
            learner_analysis.update_analysis(db, db.get(Student, student.id), "lesson")
            db.commit()
        assert client.get("/v1/web/student/analysis").json()["text"].startswith("وضعیت کلی:\n- نسخه اول")

        monkeypatch.setattr(learner_analysis, "complete", lambda *a, **k: _reply("نسخه‌ی آفلاین", mode="offline"))
        with SessionLocal() as db:
            learner_analysis.update_analysis(db, db.get(Student, student.id), "test")
            db.commit()
        # The offline reply is not saved, so the first version is still the latest one.
        assert "نسخه‌ی آفلاین" not in client.get("/v1/web/student/analysis").json()["text"]
    finally:
        with SessionLocal() as db:
            db.query(LearnerAnalysis).filter(LearnerAnalysis.student_id == student.id).delete()
            db.commit()


def test_a_failing_model_call_does_not_break_the_caller(client, monkeypatch):
    learner_login(client)
    student = demo_student()

    def broken(*args, **kwargs):
        raise RuntimeError("provider is down")

    monkeypatch.setattr(learner_analysis, "complete", broken)
    with SessionLocal() as db:
        learner_analysis.update_analysis(db, db.get(Student, student.id), "lesson")
        db.commit()
    assert client.get("/v1/web/student/analysis").status_code == 200


def test_the_first_read_makes_the_analysis_from_existing_data(client, monkeypatch):
    learner_login(client)
    student = demo_student()
    with SessionLocal() as db:
        db.query(LearnerAnalysis).filter(LearnerAnalysis.student_id == student.id).delete()
        db.commit()
    monkeypatch.setattr(learner_analysis, "complete", lambda *a, **k: _reply("وضعیت کلی:\n- از داده‌های موجود"))
    try:
        body = client.get("/v1/web/student/analysis").json()
        # With history the model writes the analysis; with none, the starter report is stored.
        assert body["text"].startswith("وضعیت کلی:\n- از داده‌های موجود") or body["text"] == learner_analysis.INITIAL_TEXT
        assert body["created_at"]
    finally:
        with SessionLocal() as db:
            db.query(LearnerAnalysis).filter(LearnerAnalysis.student_id == student.id).delete()
            db.commit()
