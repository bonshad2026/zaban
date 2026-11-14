from zaban.db import SessionLocal
from zaban.models import TutorSession
from zaban.services.ai_gateway import AIResult
from zaban.services import evaluation
from test_api import DEMO, _complete_profile, _create_student, _give_consent


def test_ending_a_lesson_gives_it_a_score_at_once(client, monkeypatch):
    monkeypatch.setattr(
        evaluation,
        "complete",
        lambda *args, **kwargs: AIResult(text="Good work today.\nSCORE: 80", input_tokens=10, output_tokens=5, mode="live"),
    )
    student_id = _create_student(client, "score-at-end")
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
    assert client.post(f"/v1/sessions/{session_id}/messages", json={"content": "I like cats"}, headers=DEMO).status_code == 200

    ended = client.post(f"/v1/sessions/{session_id}/end", headers=DEMO)
    assert ended.status_code == 200, ended.text
    with SessionLocal() as db:
        session = db.get(TutorSession, session_id)
        assert session.score == 80.0
        assert session.evaluation == "Good work today."
