# Completion of docs/conversation-partner.md: the remaining learner, admin and page items.
import os

import pytest
import uuid
from datetime import timedelta

from helpers_learner import learner_login, self_student
from zaban.db import SessionLocal
from zaban.models import TutorSession, utcnow

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
CRITERIA = ["level_range", "level_accuracy", "level_fluency", "level_interaction", "level_coherence"]


def test_speaking_level_before_the_first_lesson_sets_all_five_criteria(client):
    learner_login(client)
    response = client.put("/v1/web/student/skill-levels", json={"speaking": "B1"})
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        student = self_student(db)
        assert [getattr(student, column) for column in CRITERIA] == ["B1"] * 5


def test_speaking_level_is_fixed_after_the_first_lesson(client):
    learner_login(client)
    with SessionLocal() as db:
        student = self_student(db)
        now = utcnow()
        db.add(TutorSession(student_id=student.id, duration_minutes=10, started_at=now, ends_at=now + timedelta(minutes=10), status="completed"))
        db.commit()
    response = client.put("/v1/web/student/skill-levels", json={"speaking": "C1"})
    assert response.status_code == 409


def test_time_up_leaves_the_lesson_open_until_the_learner_decides(client):
    from datetime import timedelta as _td

    from helpers_learner import PARENT_PHONE
    from zaban.models import Guardian

    learner_login(client)
    with SessionLocal() as db:
        student = self_student(db)
        owner = db.query(Guardian).filter(Guardian.phone == PARENT_PHONE).one()
        saved = (owner.plan_expires_at, owner.plan_token_allowance, owner.plan_tokens_used)
        owner.plan_expires_at = utcnow() + _td(days=30)
        owner.plan_token_allowance = 1000000
        owner.plan_tokens_used = 0
        now = utcnow()
        lesson = TutorSession(
            student_id=student.id, duration_minutes=10, started_at=now - _td(minutes=11), ends_at=now - _td(minutes=1),
            status="active", engine="new",
        )
        db.add(lesson)
        db.commit()
        lesson_id = lesson.id
    try:
        seen = client.get(f"/v1/sessions/{lesson_id}").json()
        assert seen["status"] == "completed"
        with SessionLocal() as db:
            assert db.get(TutorSession, lesson_id).end_status == "active"  # nothing is decided yet
        resumed = client.post(f"/v1/sessions/{lesson_id}/continue")
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["status"] == "active"
    finally:
        with SessionLocal() as db:
            owner = db.query(Guardian).filter(Guardian.phone == PARENT_PHONE).one()
            owner.plan_expires_at, owner.plan_token_allowance, owner.plan_tokens_used = saved
            db.commit()


def test_lesson_summary_shows_the_criteria_and_the_phrases_of_the_lesson(client):
    from zaban.models import PhraseItem, SessionLogEntry
    from zaban.services.phrase_library import add_phrase, phrase_key

    learner_login(client)
    phrase_text = f"could I get the bill {uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        student = self_student(db)
        add_phrase(db, phrase_text, "A2", source="admin")
        db.flush()
        item = db.query(PhraseItem).filter(PhraseItem.text_key == phrase_key(phrase_text)).one()
        now = utcnow()
        lesson = TutorSession(
            student_id=student.id, duration_minutes=10, started_at=now, ends_at=now + timedelta(minutes=10),
            status="completed", engine="new", end_status="evaluated", evaluation="Good lesson.",
            eval_range="B1", eval_accuracy="A2", eval_fluency="A2", eval_interaction="B1", eval_coherence="A2",
        )
        db.add(lesson)
        db.flush()
        db.add(SessionLogEntry(session_id=lesson.id, student_id=student.id, kind="phrase", key=str(item.id), detail="used", created_at=now))
        db.commit()
        lesson_id = lesson.id
    data = client.get(f"/v1/sessions/{lesson_id}/summary").json()
    assert data["summary"] == "Good lesson."
    assert data["criteria"] == {"range": "B1", "accuracy": "A2", "fluency": "A2", "interaction": "B1", "coherence": "A2"}
    assert data["phrases"] == [{"text": phrase_text, "status": "used"}]


def test_learner_sees_the_criteria_and_phrases_of_the_partner(client):
    learner_login(client)
    response = client.get("/v1/web/student/partner")
    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data["criteria"]) == {"range", "accuracy", "fluency", "interaction", "coherence"}
    assert isinstance(data["phrases"], list)


def test_mode_rules_reach_only_their_own_mode(client):
    from zaban.services.partner_settings import PARTNER_SETTINGS, mode_rules_of, normalize
    from zaban.services.partner_prompt import mode_part
    from zaban.services.settings_store import set_setting

    spec = next(s for s in PARTNER_SETTINGS if s["key"] == "partner_mode_rules")
    with pytest.raises(ValueError):
        normalize(spec, "dance: nothing")
    with pytest.raises(ValueError):
        normalize(spec, "translation without a colon")
    text = normalize(spec, "translation: say the sentence twice\nreview: use three phrases")
    assert mode_rules_of(text) == {"translation": "say the sentence twice", "review": "use three phrases"}
    with SessionLocal() as db:
        set_setting(db, "partner_mode_rules", text)
        db.commit()
        translation = mode_part(db, "translation").text
        summary = mode_part(db, "summary").text
        set_setting(db, "partner_mode_rules", "")
        db.commit()
    assert "say the sentence twice" in translation and "say the sentence twice" not in summary


def test_admin_gets_the_fixed_rules_and_the_policy_table(client):
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    fixed = client.get("/v1/admin/api/partner-fixed-rules").json()["text"]
    assert fixed.startswith("[Fixed rules]")
    rows = client.get("/v1/admin/api/partner-policy").json()
    assert [row["level"] for row in rows] == ["A1", "A2", "B1", "B2", "C1", "C2"]
    assert all(set(row) >= {"sentence", "vocab", "question", "correction", "turn"} for row in rows)


def test_notebook_rule_can_be_changed_by_the_administrator(client):
    from zaban.services.partner_settings import PARTNER_SETTINGS, normalize

    spec = next(s for s in PARTNER_SETTINGS if s["key"] == "partner_notebook_rules")
    assert normalize(spec, " Write short notes. {max_words} words at most. ") == "Write short notes. {max_words} words at most."


def test_shadowing_compares_words_not_order():
    from zaban.services.partner_shadowing import compare

    result = compare("I like green tea.", "tea I like")
    assert result["missing"] == ["green"] and result["extra"] == []  # the same words in another order still count
    assert compare("I like green tea.", "I like green tea")["score"] == 100
    check = compare("I like green tea.", "I like tea now")
    assert check["missing"] == ["green"] and check["extra"] == ["now"]


def test_partner_reads_the_shadowing_target():
    from zaban.services.partner_output import parse_output

    turn = parse_output('{"mode": "shadowing", "reply": "Repeat after me.", "target": "I like green tea.", "feedback": null, "new_phrase": null, "next_action": "continue"}')
    assert turn.valid and turn.target == "I like green tea."


def test_shadowing_turn_returns_the_target_and_the_check(client, monkeypatch):
    import json as _json

    from helpers_learner import PARENT_PHONE
    from test_api import DEMO, _complete_profile, _create_student, _give_consent
    from zaban.services.ai import TutorReply
    from zaban.models import Guardian

    replies = iter([
        _json.dumps({"mode": "shadowing", "reply": "Repeat after me.", "target": "I like green tea.", "feedback": None, "new_phrase": None, "next_action": "continue"}),
        _json.dumps({"mode": "shadowing", "reply": "Good. Next one.", "target": "Where is the bus stop?", "feedback": None, "new_phrase": None, "next_action": "continue"}),
    ])
    monkeypatch.setattr("zaban.api.tutor_reply", lambda prompt, messages: TutorReply(text=next(replies), input_tokens=5, output_tokens=5, mode="live"))
    student_id = _create_student(client, f"shadow-{uuid.uuid4().hex[:8]}")
    _give_consent(client, student_id)
    _complete_profile(student_id)
    plan = client.post(
        f"/v1/students/{student_id}/plans",
        json={"goal": "Talk about school", "months": 2, "sessions_per_week": 3, "minutes_per_session": 10},
        headers=DEMO,
    )
    assert plan.status_code == 201, plan.text
    session_id = client.post(f"/v1/students/{student_id}/sessions", json={"duration_minutes": 20}, headers=DEMO).json()["id"]
    assert client.put(
        f"/v1/sessions/{session_id}/rhythm",
        json={"parts": [{"mode": "shadowing", "minutes": 10}, {"mode": "conversation", "minutes": 10}]},
        headers=DEMO,
    ).status_code == 200
    first = client.post(f"/v1/sessions/{session_id}/messages", json={"content": "hello"}, headers=DEMO).json()
    assert first["shadowing"]["target"] == "I like green tea."
    assert first["shadowing"]["check"] is None  # nothing to compare on the first turn
    second = client.post(f"/v1/sessions/{session_id}/messages", json={"content": "I like tea"}, headers=DEMO).json()
    assert second["shadowing"]["check"]["missing"] == ["green"]


def test_prompt_sections_follow_the_example_document(client):
    from zaban.models import Tenant
    from zaban.services.partner_prompt import build_parts
    from zaban.models import Student
    from zaban.models import new_id as _new_id

    with SessionLocal() as db:
        tenant = db.query(Tenant).first()
        student = Student(id=_new_id(), tenant_id=tenant.id, external_user_id=uuid.uuid4().hex, level_range="B1")
        db.add(student)
        db.flush()
        text = "\n".join(part.text for part in build_parts(db, student, "conversation"))
        db.rollback()
    labels = ["[Fixed rules]", "[Shared rules]", "[Mode]", "[Level policy]", "[Learner data]", "[Output contract]"]
    positions = [text.index(label) for label in labels]
    assert positions == sorted(positions)


def test_a_simulated_trial_learner_moves_up_and_the_notebook_follows(client, monkeypatch):
    import json as _json

    from zaban.models import LearnerMemory, LearnerMemoryVersion, Message, Student
    from zaban.models import TutorSession as _Lesson
    from zaban.models import new_id as _new_id
    from zaban.services import partner_end
    from zaban.services.ai_gateway import AIResult
    from zaban.services.partner_end import finish_partner_session
    from zaban.services.partner_notebook import NOTEBOOK_HEADINGS
    from zaban.services.partner_prompt import build_prompt
    from zaban.models import Tenant

    notebook = "\n\n".join(f"## {heading}\nShort note." for heading in NOTEBOOK_HEADINGS)

    def fake(system, messages, max_tokens=300):
        if system.startswith("You judge"):
            body = _json.dumps({"criteria": {"range": "B1", "accuracy": "B1", "fluency": "A2", "interaction": "B1", "coherence": "A2"}, "summary": "Good progress."})
        else:
            body = notebook
        return AIResult(text=body, input_tokens=10, output_tokens=5, mode="live")

    monkeypatch.setattr(partner_end, "complete", fake)
    with SessionLocal() as db:
        tenant = db.query(Tenant).first()
        student = Student(id=_new_id(), tenant_id=tenant.id, external_user_id=uuid.uuid4().hex, display_name="trial",
                          level_range="A2", level_accuracy="A2", level_fluency="A2", level_interaction="A2", level_coherence="A2")
        db.add(student)
        db.commit()
        student_id = student.id

        def lesson(days_ago: int) -> str:
            now = utcnow()
            lesson_row = _Lesson(student_id=student_id, duration_minutes=10, started_at=now - timedelta(days=days_ago),
                                 ends_at=now - timedelta(days=days_ago) + timedelta(minutes=10), status="completed",
                                 ended_at=now - timedelta(days=days_ago), engine="new")
            db.add(lesson_row)
            db.flush()
            for turn in range(3):
                db.add(Message(session_id=lesson_row.id, role="user", content=f"I like school {turn}"))
                db.add(Message(session_id=lesson_row.id, role="assistant", content="Nice."))
            db.commit()
            return lesson_row.id

        first = lesson(3)
        assert finish_partner_session(db, db.get(_Lesson, first)) == "evaluated"
        db.refresh(db.get(Student, student_id))
        assert db.get(Student, student_id).level_accuracy == "A2"  # one lesson above is not enough

        second = lesson(2)
        assert finish_partner_session(db, db.get(_Lesson, second)) == "evaluated"
        db.refresh(db.get(Student, student_id))
        assert db.get(Student, student_id).level_accuracy == "B1"  # two lessons above: up

        third = lesson(1)
        assert finish_partner_session(db, db.get(_Lesson, third)) == "evaluated"
        versions = db.query(LearnerMemoryVersion).filter_by(student_id=student_id).count()
        assert versions == 3

        fourth = build_prompt(db, db.get(Student, student_id))
        assert "accuracy B1" in fourth
        assert db.get(LearnerMemory, student_id).text == notebook
        db.query(LearnerMemoryVersion).filter_by(student_id=student_id).delete()
        db.query(LearnerMemory).filter_by(student_id=student_id).delete()
        db.commit()
