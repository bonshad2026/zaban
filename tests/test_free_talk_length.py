# Free conversation: the learner chooses a length from the same list as a lesson, or no time limit.
from test_api import DEMO
from test_partner_phase3 import _with_plan
from zaban.db import SessionLocal
from zaban.models import TutorSession


def test_free_talk_uses_the_chosen_length_and_tells_the_prompt(client):
    student_id = _with_plan(client)
    started = client.post(f"/v1/students/{student_id}/free-conversation", json={"duration_minutes": 45}, headers=DEMO)
    assert started.status_code == 201, started.text
    body = started.json()
    assert body["duration_minutes"] == 45
    assert body["free"] is True
    with SessionLocal() as db:
        session = db.get(TutorSession, body["id"])
        assert session.start_prompt.count("This free conversation lasts 45 minutes.") == 1


def test_free_talk_without_a_length_has_no_time_limit(client):
    student_id = _with_plan(client)
    started = client.post(f"/v1/students/{student_id}/free-conversation", headers=DEMO)
    assert started.status_code == 201, started.text
    body = started.json()
    assert body["duration_minutes"] == 0
    with SessionLocal() as db:
        session = db.get(TutorSession, body["id"])
        assert "This free conversation lasts" not in session.start_prompt


def test_free_talk_only_accepts_the_lesson_lengths(client):
    student_id = _with_plan(client)
    for minutes in (4, 61, 70):
        response = client.post(f"/v1/students/{student_id}/free-conversation", json={"duration_minutes": minutes}, headers=DEMO)
        assert response.status_code == 422, response.text


def test_an_empty_model_reply_gives_a_notice_and_no_blank_message(client, monkeypatch):
    # The model can send no text. The learner gets a short notice, and no blank message is stored or sent back later.
    from zaban.api import EMPTY_REPLY_NOTICE
    from zaban.models import Message
    from zaban.services.ai import TutorReply

    student_id = _with_plan(client)
    session_id = client.post(f"/v1/students/{student_id}/free-conversation", headers=DEMO).json()["id"]
    monkeypatch.setattr(
        "zaban.api.tutor_reply",
        lambda prompt, messages: TutorReply(text="", input_tokens=5, output_tokens=0, mode="live", stop_reason="max_tokens"),
    )
    answer = client.post(f"/v1/sessions/{session_id}/messages", json={"content": "I like football very much"}, headers=DEMO)
    assert answer.status_code == 200, answer.text
    assert answer.json()["reply"] == EMPTY_REPLY_NOTICE
    with SessionLocal() as db:
        stored = [m.content for m in db.query(Message).filter(Message.session_id == session_id)]
    assert "" not in stored
    assert "I like football very much" in stored
