# Phase 2 of the conversation partner (docs/conversation-partner.md, section 15.5): end of lesson, levels, notebook, tokens.
import json
import os
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest

from zaban.db import SessionLocal
from zaban.models import LearnerMemory, LearnerMemoryVersion, Message, PhraseItem, PhraseReview, Student, Tenant, TutorSession, new_id, utcnow
from zaban.services import partner_end
from zaban.services.ai_gateway import AIResult
from zaban.services.partner_budget import reserve_reached, tokens_left, warnings
from zaban.services.partner_end import finish_partner_session, reprocess
from zaban.services.partner_levels import next_level
from zaban.services.partner_notebook import NOTEBOOK_HEADINGS, notebook_problems
from zaban.services.phrase_library import phrase_key
from zaban.services.settings_store import set_setting

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
VALID_NOTEBOOK = "\n\n".join(f"## {heading}\nنمونه‌ی کوتاه." for heading in NOTEBOOK_HEADINGS)


@pytest.fixture(autouse=True)
def _restore_settings(client):
    yield
    with SessionLocal() as db:
        for key in (
            "partner_engine", "partner_token_reserve", "partner_min_messages_eval", "partner_level_up_sessions",
            "partner_level_down_sessions", "partner_memory_max_words", "partner_token_warn_remaining", "partner_expiry_warn_days",
        ):
            set_setting(db, key, "")
        db.commit()


def _summary(**criteria: str) -> str:
    base = {"range": "A2", "accuracy": "A2", "fluency": "A2", "interaction": "A2", "coherence": "A2"}
    base.update(criteria)
    return json.dumps({"criteria": base, "summary": "A short lesson summary."})


def _fake_model(summary: str, notebook: str):
    # The routine makes two kinds of calls: the summary (its instructions name the judge: "ارزیاب مهارت گفتاری") and the notebook.
    def complete(system, messages, max_tokens=300):
        text = summary if "ارزیاب مهارت گفتاری" in system else notebook
        return AIResult(text=text, input_tokens=10, output_tokens=5, mode="live")

    return complete


def _student(db, level: str = "A2") -> Student:
    tenant = db.query(Tenant).first()
    student = Student(
        id=new_id(), tenant_id=tenant.id, external_user_id=uuid.uuid4().hex, display_name="end test",
        level_range=level, level_accuracy=level, level_fluency=level, level_interaction=level, level_coherence=level,
    )
    db.add(student)
    db.commit()
    return student


def _lesson(db, student: Student, user_turns: int = 3, ended_days_ago: int = 0) -> TutorSession:
    now = utcnow()
    session = TutorSession(
        student_id=student.id, duration_minutes=10, started_at=now, ends_at=now + timedelta(minutes=10),
        status="completed", ended_at=now - timedelta(days=ended_days_ago),
    )
    db.add(session)
    db.flush()
    for turn in range(user_turns):
        db.add(Message(session_id=session.id, role="user", content=f"I like cats {turn}"))
        db.add(Message(session_id=session.id, role="assistant", content="Nice. Tell me more."))
    db.commit()
    return session


# ---- level rule (section 5.3) ----

@pytest.mark.parametrize(
    "current, recent, expected",
    [
        ("A2", ["B1", "B1"], "B1"),          # two lessons above: up
        ("A2", ["B1"], "A2"),                # one lesson above is not enough
        ("B2", ["C1", "C1"], "C1"),
        ("C2", ["C2", "C2"], "C2"),          # never above C2
        ("B1", ["A1", "A1", "A1"], "A2"),    # three lessons below: down one step
        ("B1", ["A1", "A1"], "B1"),          # two below is not enough
        ("A1", ["A1", "A1", "A1"], "A1"),    # never below A1
        ("B1", ["A2", "B1", "A2"], "B1"),    # mixed: no change
    ],
)
def test_level_moves_after_the_set_number_of_lessons(current, recent, expected):
    assert next_level(current, recent, up=2, down=3) == expected


# ---- notebook checks (section 14.4) ----

def test_a_complete_notebook_passes():
    assert notebook_problems(VALID_NOTEBOOK, 800, "end test") == []


def test_notebook_problems_are_named():
    missing = VALID_NOTEBOOK.replace("## خلاصه\n", "")
    problems = notebook_problems(missing, 800)
    assert any("خلاصه" in p for p in problems)
    assert any("longer" in p for p in notebook_problems(VALID_NOTEBOOK, 3))
    assert "contains a long number" in notebook_problems(VALID_NOTEBOOK + " 09121234567", 800)
    assert "contains an email address" in notebook_problems(VALID_NOTEBOOK + " a@b.com", 800)
    assert "contains the learner's name" in notebook_problems(VALID_NOTEBOOK + " end test", 800, "end test")


# ---- end routine (section 15.5 and 13.7) ----

def test_lesson_is_evaluated_and_all_parts_are_saved(client, monkeypatch):
    monkeypatch.setattr(partner_end, "complete", _fake_model(_summary(accuracy="B1"), VALID_NOTEBOOK))
    with SessionLocal() as db:
        student = _student(db)
        session = _lesson(db, student)
        assert finish_partner_session(db, session) == "evaluated"
        db.refresh(session)
        db.refresh(student)
        assert session.evaluation == "A short lesson summary."
        assert session.eval_accuracy == "B1"
        assert db.get(LearnerMemory, student.id).text == VALID_NOTEBOOK
        versions = db.query(LearnerMemoryVersion).filter_by(student_id=student.id).all()
        assert [v.event for v in versions] == ["session_end"]
        db.query(LearnerMemoryVersion).filter_by(student_id=student.id).delete()
        db.query(LearnerMemory).filter_by(student_id=student.id).delete()
        db.commit()


def test_level_moves_up_after_two_lessons(client, monkeypatch):
    monkeypatch.setattr(partner_end, "complete", _fake_model(_summary(accuracy="B1"), VALID_NOTEBOOK))
    with SessionLocal() as db:
        student = _student(db, "A2")
        for days in (2, 1):  # two earlier evaluated lessons, both B1 in accuracy
            earlier = _lesson(db, student, ended_days_ago=days)
            earlier.end_status = "evaluated"
            earlier.eval_accuracy = "B1"
        current = _lesson(db, student)
        finish_partner_session(db, current)
        db.refresh(student)
        assert student.level_accuracy == "B1"
        assert student.level_range == "A2"  # the other criteria stay as they were
        db.query(LearnerMemoryVersion).filter_by(student_id=student.id).delete()
        db.query(LearnerMemory).filter_by(student_id=student.id).delete()
        db.commit()


def test_a_refused_notebook_saves_nothing(client, monkeypatch):
    # The notebook has no headings, so it is refused twice. Then the level change of the same run must not be kept.
    monkeypatch.setattr(partner_end, "complete", _fake_model(_summary(accuracy="B1"), "just text"))
    with SessionLocal() as db:
        student = _student(db, "A2")
        session = _lesson(db, student)
        assert finish_partner_session(db, session) == "pending"
        db.refresh(session)
        db.refresh(student)
        assert session.end_attempts == 1
        assert session.evaluation is None and session.eval_accuracy is None
        assert student.level_accuracy == "A2"
        assert db.get(LearnerMemory, student.id) is None


def test_pending_lesson_is_tried_again_and_then_closed_without_evaluation(client, monkeypatch):
    monkeypatch.setattr(partner_end, "complete", _fake_model(_summary(), "bad"))
    with SessionLocal() as db:
        student = _student(db)
        session = _lesson(db, student)
        for expected in ("pending", "pending", "no_evaluation"):
            assert finish_partner_session(db, session) == expected
        db.refresh(session)
        assert session.end_attempts == 3


def test_retry_after_a_failure_succeeds(client, monkeypatch):
    monkeypatch.setattr(partner_end, "complete", _fake_model(_summary(), "bad"))
    with SessionLocal() as db:
        student = _student(db)
        session = _lesson(db, student)
        assert finish_partner_session(db, session) == "pending"
    monkeypatch.setattr(partner_end, "complete", _fake_model(_summary(), VALID_NOTEBOOK))
    with SessionLocal() as db:
        session = db.get(TutorSession, session.id)
        assert reprocess(db, session) == "evaluated"
        db.query(LearnerMemoryVersion).filter_by(student_id=session.student_id).delete()
        db.query(LearnerMemory).filter_by(student_id=session.student_id).delete()
        db.commit()


def test_short_lesson_gets_no_evaluation(client, monkeypatch):
    monkeypatch.setattr(partner_end, "complete", _fake_model(_summary(), VALID_NOTEBOOK))
    with SessionLocal() as db:
        student = _student(db)
        session = _lesson(db, student, user_turns=1)
        assert finish_partner_session(db, session) == "no_evaluation"
        db.refresh(session)
        assert session.eval_range is None and db.get(LearnerMemory, student.id) is None



# ---- token budget (section 13.7) ----

def _owner(**fields):
    base = {"plan_token_allowance": 1000, "plan_tokens_used": 0, "plan_expires_at": None}
    base.update(fields)
    return SimpleNamespace(**base)


def test_token_warning_at_the_highest_threshold_reached(client):
    now = utcnow()
    with SessionLocal() as db:
        assert warnings(db, _owner(plan_tokens_used=850), now) == [{"kind": "tokens", "remaining_percent": 15, "threshold": 20}]
        assert warnings(db, _owner(plan_tokens_used=950), now) == [{"kind": "tokens", "remaining_percent": 5, "threshold": 10}]
        assert warnings(db, _owner(plan_tokens_used=100), now) == []


def test_expiry_warning_close_to_the_end_date(client):
    now = utcnow()
    with SessionLocal() as db:
        soon = _owner(plan_expires_at=now + timedelta(days=2, hours=1))
        assert warnings(db, soon, now) == [{"kind": "expiry", "days_left": 2}]
        assert warnings(db, _owner(plan_expires_at=now + timedelta(days=30)), now) == []


def test_reserve_closes_the_lesson_before_the_plan_is_used_up(client):
    with SessionLocal() as db:
        set_setting(db, "partner_token_reserve", "100")
        db.commit()
        owner = _owner(plan_token_allowance=1000, plan_tokens_used=890)
        assert tokens_left(owner) == 110 and reserve_reached(db, owner) is False
        owner.plan_tokens_used = 900
        assert reserve_reached(db, owner) is True
        assert reserve_reached(db, None) is False


# ---- admin endpoints ----

def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def test_admin_edits_the_notebook_and_reverts_it(client):
    _admin(client)
    with SessionLocal() as db:
        student_id = _student(db).id
        db.commit()
    url = f"/v1/admin/api/learners/{student_id}/partner"
    assert client.post(f"{url}/notebook", json={"text": "no headings here"}).status_code == 400
    assert client.post(f"{url}/notebook", json={"text": VALID_NOTEBOOK}).status_code == 200
    assert client.post(f"{url}/notebook", json={"text": VALID_NOTEBOOK.replace("نمونه", "نمونه ۲")}).status_code == 200
    data = client.get(url).json()
    assert data["notebook"] == VALID_NOTEBOOK.replace("نمونه", "نمونه ۲")
    events = [v["event"] for v in data["versions"]]
    assert events == ["admin_edit", "admin_edit"]
    first = data["versions"][-1]["id"]
    assert client.post(f"{url}/notebook/revert", json={"version_id": first}).status_code == 200
    assert client.get(url).json()["notebook"] == VALID_NOTEBOOK
    assert client.get(url).json()["versions"][0]["event"] == "revert"


def test_admin_criteria_must_be_levels(client):
    _admin(client)
    with SessionLocal() as db:
        student_id = _student(db).id
        db.commit()
    url = f"/v1/admin/api/learners/{student_id}/partner/criteria"
    assert client.post(url, json={"values": {"range": "Z9"}}).status_code == 400
    assert client.post(url, json={"values": {"range": "B2"}}).status_code == 200
    assert client.get(f"/v1/admin/api/learners/{student_id}/partner").json()["criteria"]["range"] == "B2"



def test_admin_adds_a_reviewed_phrase_to_the_library(client):
    _admin(client)
    text = f"could you say that again {uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        review = PhraseReview(text=text, text_key=phrase_key(text), situation="asking again", register="casual")
        db.add(review)
        db.commit()
        review_id = review.id
    assert client.post(f"/v1/admin/api/phrase-review/{review_id}", json={"action": "add"}).status_code == 400
    assert client.post(f"/v1/admin/api/phrase-review/{review_id}", json={"action": "add", "level": "A2", "tone": "casual"}).status_code == 200
    with SessionLocal() as db:
        item = db.query(PhraseItem).filter_by(text_key=phrase_key(text)).one()
        assert item.level == "A2" and item.source == "review" and item.register == "casual"
        db.query(PhraseItem).filter_by(text_key=phrase_key(text)).delete()
        db.query(PhraseReview).filter_by(id=review_id).delete()
        db.commit()
