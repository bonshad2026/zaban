# Phase 4 of the conversation partner (docs/conversation-partner.md, section 15.7): «خودت رو محک بزن» in the new routine.
import os
import uuid
from datetime import timedelta

import pytest

from zaban.db import SessionLocal
from zaban.models import LearnerError, LearnerMemory, LearnerMemoryVersion, LearnerPhrase, SelfTest, SelfTestMessage, Student, Tenant, new_id, utcnow
from zaban.services import partner_end, self_test
from zaban.services.ai_gateway import AIResult
from zaban.services.partner_notebook import NOTEBOOK_HEADINGS
from zaban.services.partner_settings import PARTNER_SETTINGS
from zaban.services.self_test import finish_test
from zaban.services.self_test_prompt import build_prompt
from zaban.services.settings_store import set_setting

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
VALID_NOTEBOOK = "\n\n".join(f"## {heading}\nنمونه‌ی کوتاه." for heading in NOTEBOOK_HEADINGS)
REPORT = "Good work.\nSCORE: 70"


@pytest.fixture(autouse=True)
def _restore_settings(client):
    yield
    with SessionLocal() as db:
        for spec in PARTNER_SETTINGS:
            set_setting(db, spec["key"], "")
        set_setting(db, "partner_engine", "")
        db.commit()


def _summary(**criteria: str) -> str:
    base = {"range": "A2", "accuracy": "A2", "fluency": "A2", "interaction": "A2", "coherence": "A2"}
    base.update(criteria)
    import json

    return json.dumps({"criteria": base, "summary": "A short test summary."})


def _fake_partner(summary: str, notebook: str):
    def complete(system, messages, max_tokens=300):
        text = summary if system.startswith("You judge") else notebook
        return AIResult(text=text, input_tokens=10, output_tokens=5, mode="live")

    return complete


def _student(db, level: str = "A2") -> Student:
    tenant = db.query(Tenant).first()
    student = Student(
        id=new_id(), tenant_id=tenant.id, external_user_id=uuid.uuid4().hex, display_name="test learner",
        level_range=level, level_accuracy=level, level_fluency=level, level_interaction=level, level_coherence=level,
    )
    db.add(student)
    db.commit()
    return student


def _test(db, student: Student, skill: str, ago_days: int = 0, partner_status: str = "", **criteria) -> SelfTest:
    now = utcnow()
    test = SelfTest(
        student_id=student.id, kind="qa", skill=skill, minutes=10, level_used="A2", status="active",
        ends_at=now + timedelta(minutes=10), created_at=now - timedelta(days=ago_days), partner_status=partner_status,
    )
    for key, value in criteria.items():
        setattr(test, f"eval_{key}", value)
    db.add(test)
    db.flush()
    db.add(SelfTestMessage(test_id=test.id, role="user", content="I like cats and I go to school every day."))
    db.add(SelfTestMessage(test_id=test.id, role="assistant", content="Nice. Where do you study?"))
    db.commit()
    return test


def _finish(monkeypatch, test_id: str, skill_summary: str, notebook: str, engine: str = "new") -> SelfTest:
    monkeypatch.setattr(self_test, "complete", lambda *a, **k: AIResult(text=REPORT, input_tokens=10, output_tokens=5, mode="live"))
    monkeypatch.setattr(partner_end, "complete", _fake_partner(skill_summary, notebook))
    with SessionLocal() as db:
        set_setting(db, "partner_engine", engine)
        db.commit()
        student = db.get(Student, db.get(SelfTest, test_id).student_id)
        test = db.get(SelfTest, test_id)
        finish_test(db, student, test)
        return db.get(SelfTest, test_id)


def test_speaking_test_moves_the_level_and_updates_the_notebook(client, monkeypatch):
    with SessionLocal() as db:
        student = _student(db, "A2")
        _test(db, student, "speaking", ago_days=2, partner_status="evaluated", accuracy="B1")
        _test(db, student, "speaking", ago_days=1, partner_status="evaluated", accuracy="B1")
        test = _test(db, student, "speaking")
        student_id, test_id = student.id, test.id
    test = _finish(monkeypatch, test_id, _summary(accuracy="B1"), VALID_NOTEBOOK)
    assert test.status == "finished" and test.score == 70
    assert test.partner_status == "evaluated" and test.eval_accuracy == "B1"
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        assert student.level_accuracy == "B1"
        assert db.get(LearnerMemory, student_id).text == VALID_NOTEBOOK
        assert [v.event for v in db.query(LearnerMemoryVersion).filter_by(student_id=student_id).all()] == ["self_test"]


def test_writing_test_updates_the_notebook_but_not_the_levels(client, monkeypatch):
    with SessionLocal() as db:
        student = _student(db, "A2")
        test = _test(db, student, "writing")
        student_id, test_id = student.id, test.id
    test = _finish(monkeypatch, test_id, _summary(accuracy="B1"), VALID_NOTEBOOK)
    assert test.partner_status == "evaluated" and test.eval_range is None
    with SessionLocal() as db:
        assert db.get(Student, student_id).level_accuracy == "A2"
        assert db.get(LearnerMemory, student_id) is not None


def test_refused_notebook_keeps_the_report_and_saves_nothing_else(client, monkeypatch):
    with SessionLocal() as db:
        student = _student(db, "A2")
        _test(db, student, "speaking", ago_days=2, partner_status="evaluated", accuracy="B1")
        _test(db, student, "speaking", ago_days=1, partner_status="evaluated", accuracy="B1")
        test = _test(db, student, "speaking")
        student_id, test_id = student.id, test.id
    test = _finish(monkeypatch, test_id, _summary(accuracy="B1"), "no headings")
    assert test.status == "finished" and test.score == 70  # the report stays
    assert test.partner_status == "pending" and test.partner_attempts == 1
    assert test.eval_accuracy is None
    with SessionLocal() as db:
        assert db.get(Student, student_id).level_accuracy == "A2"
        assert db.get(LearnerMemory, student_id) is None


def test_the_test_does_not_write_phrases_or_errors(client, monkeypatch):
    with SessionLocal() as db:
        student = _student(db)
        test = _test(db, student, "mixed")
        student_id, test_id = student.id, test.id
    _finish(monkeypatch, test_id, _summary(), VALID_NOTEBOOK)
    with SessionLocal() as db:
        assert db.query(LearnerError).filter_by(student_id=student_id).count() == 0
        assert db.query(LearnerPhrase).filter_by(student_id=student_id).count() == 0


def test_the_self_test_prompt_reads_the_notebook(client):
    with SessionLocal() as db:
        student = _student(db)
        db.add(LearnerMemory(student_id=student.id, text="MARK-NOTEBOOK-TEXT"))
        db.commit()
        text, _ = build_prompt(db, student, "qa", "qa", "speaking", 10, "A2")
    assert "MARK-NOTEBOOK-TEXT" in text


def test_admin_tries_a_waiting_test_again(client, monkeypatch):
    with SessionLocal() as db:
        student = _student(db)
        test = _test(db, student, "writing")
        student_id, test_id = student.id, test.id
    _finish(monkeypatch, test_id, _summary(), "no headings")
    with SessionLocal() as db:
        assert db.get(SelfTest, test_id).partner_status == "pending"
    monkeypatch.setattr(partner_end, "complete", _fake_partner(_summary(), VALID_NOTEBOOK))
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    response = client.post(f"/v1/admin/api/self-tests/{test_id}/reprocess")
    assert response.status_code == 200, response.text
    assert response.json() == {"partner_status": "evaluated"}
