# Phase 3 of the conversation partner (docs/conversation-partner.md, section 15.6): free conversation, lesson rhythm, translation timing.
import json
import os
import uuid
from datetime import timedelta

import pytest

from test_api import DEMO, _complete_profile, _create_student, _give_consent
from zaban.db import SessionLocal
from zaban.models import TutorSession, utcnow
from zaban.services import partner_prompt
from zaban.services.ai import TutorReply
from zaban.services.partner_prompt import sentence_seconds, turn_block
from zaban.services.partner_rhythm import move, segment_state, split_minutes, validate_rhythm
from zaban.services.partner_settings import PARTNER_SETTINGS
from zaban.services.settings_store import set_setting

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
DEFAULT_RHYTHM = "conversation:60,translation:20,review:10,summary:10"


@pytest.fixture(autouse=True)
def _restore_settings(client):
    yield
    with SessionLocal() as db:
        for spec in PARTNER_SETTINGS:
            set_setting(db, spec["key"], "")
        set_setting(db, "partner_engine", "")
        db.commit()


def _lesson(duration: int = 20, started_minutes_ago: int = 0) -> TutorSession:
    now = utcnow()
    started = now - timedelta(minutes=started_minutes_ago)
    session = TutorSession(duration_minutes=duration, started_at=started, ends_at=started + timedelta(minutes=duration))
    session.rhythm = json.dumps(split_minutes(DEFAULT_RHYTHM, duration))
    session.mode_index = 0
    session.mode_started_at = started
    return session


# ---- rhythm arithmetic (section 4.15) ----

@pytest.mark.parametrize("duration", [10, 20, 45, 60])
def test_default_rhythm_adds_up_to_the_lesson_length(duration):
    parts = split_minutes(DEFAULT_RHYTHM, duration)
    assert sum(part["minutes"] for part in parts) == duration
    assert all(part["minutes"] >= 1 for part in parts)


def test_twenty_minute_lesson_gives_the_example_of_the_design():
    assert [(p["mode"], p["minutes"]) for p in split_minutes(DEFAULT_RHYTHM, 20)] == [
        ("conversation", 12), ("translation", 4), ("review", 2), ("summary", 2),
    ]


def test_running_part_and_the_one_after_it():
    session = _lesson(20, started_minutes_ago=13)  # 12 minutes of conversation are over
    state = segment_state(session, utcnow())
    assert state["mode"] == "conversation" and state["over"] is True
    assert state["next_mode"] == "translation"
    assert state["label"] == "گفتگو"


def test_move_to_next_and_back_to_current_starts_the_time_again():
    session = _lesson(20, started_minutes_ago=13)
    now = utcnow()
    move(session, now, "next")
    state = segment_state(session, now)
    assert state["mode"] == "translation" and state["over"] is False
    move(session, now, "current")
    assert segment_state(session, now)["mode"] == "translation"


def test_jump_to_a_named_part_and_refuse_bad_moves():
    session = _lesson(20)
    move(session, utcnow(), "summary")
    assert segment_state(session, utcnow())["mode"] == "summary"
    with pytest.raises(ValueError):
        move(session, utcnow(), "shadowing")
    with pytest.raises(ValueError):
        move(session, utcnow(), "next")  # summary is the last part


@pytest.mark.parametrize(
    "parts",
    [
        [{"mode": "dance", "minutes": 5}],
        [{"mode": "conversation", "minutes": 0}],
        [{"mode": "conversation", "minutes": 15}, {"mode": "translation", "minutes": 10}],
        [{"mode": "conversation", "minutes": 1}] * 9,
        [],
    ],
)
def test_bad_rhythm_edits_are_refused(parts):
    with pytest.raises(ValueError):
        validate_rhythm(parts, 20)


def test_a_good_edit_is_kept_in_its_order():
    parts = validate_rhythm([{"mode": "translation", "minutes": 10}, {"mode": "conversation", "minutes": 8}], 20)
    assert parts == [{"mode": "translation", "minutes": 10}, {"mode": "conversation", "minutes": 8}]


# ---- translation timing and the turn block (section 4.2) ----

def test_sentence_time_follows_the_fluency_level(client):
    from zaban.models import Student

    with SessionLocal() as db:
        student = Student(id="x", tenant_id="t", external_user_id="x", level_fluency="B1")
        assert sentence_seconds(db, student) == 10
        student.level_fluency = "B2"
        assert sentence_seconds(db, student) == 7


def test_turn_block_shows_limits_only_where_they_apply():
    with_limit = turn_block("translation", "main_practice", 90, 15)
    assert "Time left in this part: 90 seconds" in with_limit
    assert "Time for one sentence: 15 seconds" in with_limit
    free = turn_block("conversation", "warm_up", None)
    assert "no limit" in free and "Time for one sentence" not in free


def test_free_conversation_rules_only_reach_free_conversation(client):
    with SessionLocal() as db:
        set_setting(db, "partner_free_rules", "FREE-RULE-MARK")
        db.commit()
        free = partner_prompt.mode_part(db, "conversation", free=True).text
        lesson = partner_prompt.mode_part(db, "conversation", free=False).text
    assert "FREE-RULE-MARK" in free and "FREE-RULE-MARK" not in lesson


def test_unknown_mode_is_refused(client):
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            partner_prompt.mode_part(db, "shadowing")


# ---- routes ----

def _with_plan(client) -> str:
    student_id = _create_student(client, f"phase3-{uuid.uuid4().hex[:8]}")
    _give_consent(client, student_id)
    _complete_profile(student_id)
    plan = client.post(
        f"/v1/students/{student_id}/plans",
        json={"goal": "Talk about school", "months": 2, "sessions_per_week": 3, "minutes_per_session": 10},
        headers=DEMO,
    )
    assert plan.status_code == 201, plan.text
    return student_id


def test_lesson_rhythm_can_be_read_moved_and_edited(client, monkeypatch):
    reply_json = json.dumps({"mode": "conversation", "reply": "Good.", "feedback": None, "new_phrase": None, "next_action": "continue"})
    monkeypatch.setattr("zaban.api.tutor_reply", lambda prompt, messages: TutorReply(text=reply_json, input_tokens=5, output_tokens=5, mode="live"))
    with SessionLocal() as db:
        set_setting(db, "partner_engine", "new")
        db.commit()
    student_id = _with_plan(client)
    lesson = client.post(f"/v1/students/{student_id}/sessions", json={"duration_minutes": 20}, headers=DEMO)
    session_id = lesson.json()["id"]

    state = client.get(f"/v1/sessions/{session_id}/rhythm", headers=DEMO).json()
    assert state["mode"] == "conversation" and [p["minutes"] for p in state["parts"]] == [12, 4, 2, 2]

    assert client.put(f"/v1/sessions/{session_id}/rhythm", json={"parts": [{"mode": "conversation", "minutes": 30}]}, headers=DEMO).status_code == 400
    edited = client.put(
        f"/v1/sessions/{session_id}/rhythm",
        json={"parts": [{"mode": "translation", "minutes": 8}, {"mode": "conversation", "minutes": 12}]},
        headers=DEMO,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["mode"] == "translation" and edited.json()["label"] == "ترجمه‌ی ذهنی"

    moved = client.post(f"/v1/sessions/{session_id}/rhythm/move", json={"to": "next"}, headers=DEMO)
    assert moved.status_code == 200 and moved.json()["mode"] == "conversation"

    answer = client.post(f"/v1/sessions/{session_id}/messages", json={"content": "I like cats"}, headers=DEMO).json()
    assert answer["rhythm"]["mode"] == "conversation"


def test_free_conversation_has_no_time_and_uses_the_free_rules(client, monkeypatch):
    prompts = []

    def fake_reply(prompt, messages):
        prompts.append(prompt)
        return TutorReply(
            text=json.dumps({"mode": "conversation", "reply": "Hi!", "feedback": None, "new_phrase": None, "next_action": "continue"}),
            input_tokens=5, output_tokens=5, mode="live",
        )

    monkeypatch.setattr("zaban.api.tutor_reply", fake_reply)
    with SessionLocal() as db:
        set_setting(db, "partner_free_rules", "FREE-RULE-MARK")
        db.commit()
    student_id = _with_plan(client)
    started = client.post(f"/v1/students/{student_id}/free-conversation", headers=DEMO)
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]

    answer = client.post(f"/v1/sessions/{session_id}/messages", json={"content": "Hello"}, headers=DEMO)
    assert answer.status_code == 200, answer.text
    assert answer.json()["rhythm"] is None
    assert "FREE-RULE-MARK" in prompts[-1] and "no limit" in prompts[-1]
    assert client.get(f"/v1/sessions/{session_id}/rhythm", headers=DEMO).json() == {"rhythm": None}
    with SessionLocal() as db:
        session = db.get(TutorSession, session_id)
        assert session.session_kind == "free" and session.engine == "new"
    with SessionLocal() as db:
        set_setting(db, "partner_free_rules", "")
        db.commit()
