import os

from zaban.db import SessionLocal
from zaban.models import Tenant
from zaban.services.progress import cefr_from_score, progress_status

DEMO = {"X-API-Key": os.environ["ZABAN_DEMO_API_KEY"]}


def _create_student(client, external_id: str = "student-001") -> str:
    response = client.post(
        "/v1/students",
        json={"external_user_id": external_id, "age_band": "11-14"},
        headers=DEMO,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _give_consent(client, student_id: str) -> None:
    response = client.post(f"/v1/students/{student_id}/consent", json={"accepted": True}, headers=DEMO)
    assert response.status_code == 201, response.text


def test_requests_without_key_are_rejected(client):
    response = client.post("/v1/students", json={"external_user_id": "x", "age_band": "adult"})
    assert response.status_code == 401


def test_lesson_requires_parent_consent(client):
    student_id = _create_student(client, "no-consent")
    response = client.post(f"/v1/students/{student_id}/sessions", json={"duration_minutes": 10}, headers=DEMO)
    assert response.status_code == 403


def test_full_lesson_flow_and_reports(client):
    student_id = _create_student(client, "full-flow")
    _give_consent(client, student_id)

    placement = client.post(f"/v1/students/{student_id}/placement", json={"score": 45}, headers=DEMO)
    assert placement.json()["cefr_level"] == "B1"

    plan = client.post(
        f"/v1/students/{student_id}/plans",
        json={"goal": "Talk about school", "months": 5, "sessions_per_week": 3, "minutes_per_session": 10},
        headers=DEMO,
    )
    assert plan.status_code == 201, plan.text
    assert len(plan.json()["milestones"]) == 5

    lesson = client.post(f"/v1/students/{student_id}/sessions", json={"duration_minutes": 10}, headers=DEMO)
    assert lesson.status_code == 201, lesson.text
    session_id = lesson.json()["id"]

    reply = client.post(f"/v1/sessions/{session_id}/messages", json={"content": "I like football"}, headers=DEMO)
    assert reply.status_code == 200
    assert reply.json()["mode"] == "offline"
    assert reply.json()["guarded"] is None

    blocked = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"content": "Visit https://example.com now"},
        headers=DEMO,
    )
    assert blocked.json()["guarded"] == "links"
    assert blocked.json()["mode"] is None

    ended = client.post(f"/v1/sessions/{session_id}/end", headers=DEMO)
    assert ended.json()["status"] == "completed"
    assert ended.json()["score"] is not None

    progress = client.get(f"/v1/students/{student_id}/reports/progress", headers=DEMO)
    assert progress.status_code == 200
    assert progress.json()["status"] == "insufficient_data"
    assert len(progress.json()["sessions"]) == 1

    parent = client.get(f"/v1/students/{student_id}/reports/parent", headers=DEMO)
    assert parent.status_code == 200
    assert parent.json()["summary_fa"]

    usage = client.get("/v1/tenant/usage", headers=DEMO)
    assert usage.status_code == 200
    assert usage.json()["used_tokens"] >= 1


def test_student_token_only_reaches_own_data(client):
    first = _create_student(client, "token-a")
    second = _create_student(client, "token-b")
    _give_consent(client, first)

    token_response = client.post("/v1/auth/student-token", json={"student_id": first}, headers=DEMO)
    assert token_response.status_code == 200
    bearer = {"Authorization": f"Bearer {token_response.json()['token']}"}

    assert client.get(f"/v1/students/{first}/reports/progress", headers=bearer).status_code == 200
    assert client.get(f"/v1/students/{second}/reports/progress", headers=bearer).status_code == 403
    assert client.get(f"/v1/students/{first}/reports/parent", headers=bearer).status_code == 403


def test_quota_exhaustion_blocks_new_lessons(client):
    student_id = _create_student(client, "quota")
    _give_consent(client, student_id)

    with SessionLocal() as db:
        tenant = db.query(Tenant).filter(Tenant.name == "Demo Tenant").one()
        original_quota = tenant.quota_tokens
        tenant.quota_tokens = tenant.used_tokens
        db.commit()
    try:
        response = client.post(f"/v1/students/{student_id}/sessions", json={"duration_minutes": 10}, headers=DEMO)
        assert response.status_code == 402
    finally:
        with SessionLocal() as db:
            tenant = db.query(Tenant).filter(Tenant.name == "Demo Tenant").one()
            tenant.quota_tokens = original_quota
            db.commit()


def test_delete_student_removes_their_data(client):
    student_id = _create_student(client, "to-delete")
    response = client.delete(f"/v1/students/{student_id}", headers=DEMO)
    assert response.status_code == 204
    assert client.get(f"/v1/students/{student_id}/reports/progress", headers=DEMO).status_code == 404


def test_cefr_bands():
    assert cefr_from_score(0) == "A1"
    assert cefr_from_score(45) == "B1"
    assert cefr_from_score(100) == "C1"


def test_progress_status_thresholds():
    assert progress_status(50, None) == "insufficient_data"
    assert progress_status(50, 70) == "ahead"
    assert progress_status(50, 45) == "on_track"
    assert progress_status(50, 30) == "behind"
    assert progress_status(50, 10) == "well_behind"
