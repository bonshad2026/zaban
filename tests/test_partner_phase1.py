# Phase 1 of the conversation partner (docs/conversation-partner.md, section 15.4): prompt, output contract, turn logs, lesson route.
import json
import os
import uuid
from datetime import timedelta

import pytest

from test_api import DEMO, _complete_profile, _create_student, _give_consent
from zaban.db import SessionLocal
from zaban.models import LearnerError, LearnerPhrase, PhraseItem, PhraseReview, SessionLogEntry, Student, Tenant, TutorSession, new_id, utcnow
from zaban.services import partner_prompt
from zaban.services.ai import TutorReply
from zaban.services.partner_output import parse_output
from zaban.services.partner_policy import behaviour_for, parse_override, policy_table
from zaban.services.partner_settings import PARTNER_SETTINGS, normalize
from zaban.services.partner_turns import apply_turn
from zaban.services.phrase_library import add_phrase, phrase_key
from zaban.services.settings_store import set_setting

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture(autouse=True)
def _restore_partner_settings(client):
    yield
    with SessionLocal() as db:
        for spec in PARTNER_SETTINGS:
            set_setting(db, spec["key"], "")
        set_setting(db, "partner_engine", "")
        db.commit()


def _json_reply(**fields) -> str:
    base = {"mode": "conversation", "reply": "Nice. Where do you work?", "feedback": None, "new_phrase": None, "next_action": "continue"}
    base.update(fields)
    return json.dumps(base)


def _new_student(db, level: str = "B1") -> Student:
    # A learner of the test tenant. Each call is a new learner, so tests do not share rows.
    tenant = db.query(Tenant).first()
    student = Student(
        id=new_id(), tenant_id=tenant.id, external_user_id=uuid.uuid4().hex, display_name="partner test",
        level_range=level, level_accuracy="A2", level_fluency="A2", level_interaction="A2", level_coherence="A2",
    )
    db.add(student)
    db.flush()
    return student


def _session(db, student: Student) -> TutorSession:
    now = utcnow()
    session = TutorSession(student_id=student.id, duration_minutes=10, started_at=now, ends_at=now + timedelta(minutes=10))
    db.add(session)
    db.flush()
    return session


def _library_phrase(db, text: str) -> PhraseItem:
    add_phrase(db, text, "A2", situation="test", source="admin")
    db.flush()
    return db.query(PhraseItem).filter(PhraseItem.text_key == phrase_key(text)).one()


# ---- level policy ----

def test_default_policy_gives_the_behaviour_of_each_criterion():
    table = policy_table("")
    behaviour = behaviour_for(table, {"level_range": "B1", "level_accuracy": "A1", "level_fluency": "A2", "level_interaction": "B2", "level_coherence": "B2"})
    assert behaviour.vocab == table["B1"]["vocab"]
    assert behaviour.sentence == table["A1"]["sentence"]
    assert behaviour.question == table["B2"]["question"]
    assert behaviour.turn == table["A2"]["turn"]
    assert behaviour.connectors == "however, although, on the other hand"
    assert behaviour.persian.startswith("one short Persian sentence")  # the lowest criterion is A1


def test_override_line_replaces_one_level_only():
    table = policy_table("A1 | two words | very common | yes/no | say it plainly | one sentence")
    assert table["A1"]["sentence"] == "two words"
    assert table["A2"] == policy_table("")["A2"]


@pytest.mark.parametrize("text", ["Z1 | a | b | c | d | e", "A1 | a | b | c | d", "A1 | a | | c | d | e"])
def test_bad_override_lines_are_refused(text):
    with pytest.raises(ValueError):
        parse_override(text)


def test_settings_refuse_a_bad_policy_and_keep_a_good_one():
    spec = next(s for s in PARTNER_SETTINGS if s["key"] == "partner_level_policy")
    with pytest.raises(ValueError):
        normalize(spec, "A1 | only one value")
    assert normalize(spec, "A1 | a | b | c | d | e") == "A1 | a | b | c | d | e"


# ---- five-part prompt ----

def test_prompt_has_five_parts_in_order(client):
    with SessionLocal() as db:
        student = _new_student(db)
        parts = partner_prompt.build_parts(db, student, "conversation")
    assert [part.name for part in parts] == ["core", "mode", "policy", "learner", "contract"]
    assert parts[0].text.startswith("Core rules")
    assert "Shared rules:" in parts[0].text
    assert "range B1" in parts[2].text
    assert "Teacher notebook" in parts[3].text
    assert "next_action" in parts[4].text


def test_unavailable_mode_is_refused(client):
    with SessionLocal() as db:
        student = _new_student(db)
        with pytest.raises(ValueError):
            partner_prompt.build_parts(db, student, "dance")


def test_prompt_never_mentions_child_or_school_fields(client):
    with SessionLocal() as db:
        text = partner_prompt.build_prompt(db, _new_student(db))
    lowered = text.lower()
    assert "child" not in lowered and "grade" not in lowered and "school" not in lowered


# ---- output contract ----

def test_valid_json_is_read():
    turn = parse_output(_json_reply(new_phrase={"text": "I'm into…", "situation": "hobbies", "register": "casual"}))
    assert turn.valid and turn.reply == "Nice. Where do you work?"
    assert turn.new_phrase["register"] == "casual"


def test_json_inside_a_code_fence_is_read():
    assert parse_output("```json\n" + _json_reply() + "\n```").valid


def test_plain_text_is_shown_and_logs_nothing():
    turn = parse_output("Hello there, how are you?")
    assert turn.valid is False and turn.reply == "Hello there, how are you?"
    assert turn.feedback is None and turn.new_phrase is None


def test_error_type_outside_the_list_is_not_counted():
    turn = parse_output(_json_reply(feedback={"error_type": "vibes", "original": "I go yesterday", "better": "I went yesterday"}))
    assert turn.valid and turn.feedback is None


def test_unknown_register_becomes_neutral():
    turn = parse_output(_json_reply(new_phrase={"text": "Sure thing", "register": "shouty"}))
    assert turn.new_phrase["register"] == "neutral"


# ---- turn logs (database) ----

def test_error_is_counted_and_logged(client):
    with SessionLocal() as db:
        student = _new_student(db)
        session = _session(db, student)
        turn = parse_output(_json_reply(feedback={"error_type": "tense", "original": "I go yesterday", "better": "I went yesterday"}))
        apply_turn(db, student, session.id, turn, "I go yesterday", utcnow())
        row = db.query(LearnerError).filter_by(student_id=student.id, error_type="tense").one()
        assert row.count == 1
        assert db.query(SessionLogEntry).filter_by(session_id=session.id, kind="error").count() == 1
        db.rollback()


def test_new_phrase_outside_library_goes_to_review_queue(client):
    with SessionLocal() as db:
        student = _new_student(db)
        session = _session(db, student)
        turn = parse_output(_json_reply(new_phrase={"text": f"Zorblax phrase {uuid.uuid4().hex[:6]}", "situation": "test"}))
        apply_turn(db, student, session.id, turn, "hi", utcnow())
        assert db.query(PhraseReview).filter_by(text_key=phrase_key(turn.new_phrase["text"])).count() == 1
        db.rollback()


def test_phrase_is_mastered_after_clean_use_in_two_conversations(client):
    text = f"could I have a glass of water {uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        student = _new_student(db)
        item = _library_phrase(db, text)
        first, second = _session(db, student), _session(db, student)
        clean = parse_output(_json_reply())
        apply_turn(db, student, first.id, clean, text.capitalize() + ", please", utcnow())
        row = db.query(LearnerPhrase).filter_by(student_id=student.id, phrase_id=item.id).one()
        assert row.status == "used" and row.clean_sessions == 1
        apply_turn(db, student, second.id, clean, text, utcnow())
        assert row.status == "mastered" and row.next_review_at is not None
        db.rollback()


def test_use_with_a_correction_on_the_phrase_is_not_clean(client):
    text = f"that sounds great {uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        student = _new_student(db)
        item = _library_phrase(db, text)
        session = _session(db, student)
        corrected = parse_output(_json_reply(feedback={"error_type": "article", "original": text, "better": text + "!"}))
        apply_turn(db, student, session.id, corrected, text, utcnow())
        row = db.query(LearnerPhrase).filter_by(student_id=student.id, phrase_id=item.id).one()
        assert row.clean_sessions == 0 and row.status == "used"
        db.rollback()


def test_phrase_given_by_the_partner_is_seen_not_used(client):
    text = f"I'm into hiking {uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        student = _new_student(db)
        item = _library_phrase(db, text)
        session = _session(db, student)
        turn = parse_output(_json_reply(new_phrase={"text": text, "situation": "hobbies"}))
        apply_turn(db, student, session.id, turn, "I like the weather", utcnow())
        row = db.query(LearnerPhrase).filter_by(student_id=student.id, phrase_id=item.id).one()
        assert row.status == "seen"
        db.rollback()


# ---- lesson route with the new engine ----

def test_lesson_reply_is_read_from_json_when_the_partner_is_on(client, monkeypatch):
    reply_json = _json_reply(feedback={"error_type": "tense", "original": "I go yesterday", "better": "I went yesterday"})
    monkeypatch.setattr("zaban.api.tutor_reply", lambda prompt, messages: TutorReply(text=reply_json, input_tokens=10, output_tokens=5, mode="live"))
    with SessionLocal() as db:
        set_setting(db, "partner_engine", "new")
        db.commit()
    student_id = _create_student(client, "partner-route")
    _give_consent(client, student_id)
    _complete_profile(student_id)
    plan = client.post(
        f"/v1/students/{student_id}/plans",
        json={"goal": "Talk about school", "months": 2, "sessions_per_week": 3, "minutes_per_session": 10},
        headers=DEMO,
    )
    assert plan.status_code == 201, plan.text
    lesson = client.post(f"/v1/students/{student_id}/sessions", json={"duration_minutes": 10}, headers=DEMO)
    session_id = lesson.json()["id"]
    answer = client.post(f"/v1/sessions/{session_id}/messages", json={"content": "I go yesterday"}, headers=DEMO)
    assert answer.status_code == 200, answer.text
    data = answer.json()
    assert data["reply"] == "Nice. Where do you work?"
    assert data["partner"]["valid"] is True
    assert data["partner"]["feedback"]["better"] == "I went yesterday"


def test_admin_previews_the_five_parts_of_the_prompt(client):
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    with SessionLocal() as db:
        student_id = _new_student(db).id
        db.commit()
    data = client.get(f"/v1/admin/api/partner-prompt?student_id={student_id}").json()
    assert [part["name"] for part in data["parts"]] == ["core", "mode", "policy", "learner", "contract"]
    assert all(part["source"] for part in data["parts"])
    assert client.get("/v1/admin/api/partner-prompt?student_id=missing").status_code == 404
