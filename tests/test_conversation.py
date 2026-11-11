import os
from datetime import timedelta

from zaban.conversation import service
from zaban.conversation.models import ConvMessage, ConvPrompt, Conversation
from zaban.db import SessionLocal
from zaban.models import LearnerDetails, Student, utcnow
from zaban.services.settings_store import PROMPT_TOKEN_TTL_KEY, set_setting

DEMO = {"X-API-Key": os.environ["ZABAN_DEMO_API_KEY"]}


def _ready_student(client, external_id: str) -> str:
    created = client.post("/v1/students", json={"external_user_id": external_id, "age_band": "11-14"}, headers=DEMO)
    assert created.status_code == 201, created.text
    student_id = created.json()["id"]
    assert client.post(f"/v1/students/{student_id}/consent", json={"accepted": True}, headers=DEMO).status_code == 201
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        student.cefr_level = "A2"
        db.merge(LearnerDetails(student_id=student_id, age=11, gender="female"))
        db.commit()
    plan = client.post(
        f"/v1/students/{student_id}/plans",
        json={"goal": "Talk about school", "months": 2, "sessions_per_week": 3, "minutes_per_session": 10},
        headers=DEMO,
    )
    assert plan.status_code == 201, plan.text
    return student_id


def _prompt_token(client, student_id: str) -> str:
    response = client.post(f"/v1/conv/students/{student_id}/prompt", json={"duration_minutes": 10}, headers=DEMO)
    assert response.status_code == 201, response.text
    return response.json()["prompt_token"]


def _open(client, token: str) -> tuple[str, str]:
    response = client.post("/v1/conv/conversations", json={"prompt_token": token}, headers=DEMO)
    assert response.status_code == 201, response.text
    body = response.json()
    return body["conversation_id"], body["conversation_token"]


def test_prompt_is_returned_as_a_token_only(client):
    student_id = _ready_student(client, "conv-token-only")
    response = client.post(f"/v1/conv/students/{student_id}/prompt", json={"duration_minutes": 10}, headers=DEMO)
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"prompt_token", "expires_at"}
    with SessionLocal() as db:
        stored = db.query(ConvPrompt).filter(ConvPrompt.student_id == student_id).one()
        assert stored.text and stored.text not in str(body)


def test_prompt_needs_a_tenant_key(client):
    student_id = _ready_student(client, "conv-no-key")
    assert client.post(f"/v1/conv/students/{student_id}/prompt", json={}).status_code == 401


def test_prompt_token_opens_a_conversation_once(client):
    student_id = _ready_student(client, "conv-once")
    token = _prompt_token(client, student_id)
    _open(client, token)
    again = client.post("/v1/conv/conversations", json={"prompt_token": token}, headers=DEMO)
    assert again.status_code == 409


def test_bad_prompt_token_is_rejected(client):
    response = client.post("/v1/conv/conversations", json={"prompt_token": "not-a-real-token-value"}, headers=DEMO)
    assert response.status_code == 401


def test_turns_stream_a_reply_and_are_kept(client):
    student_id = _ready_student(client, "conv-turns")
    conversation_id, token = _open(client, _prompt_token(client, student_id))
    headers = {"Authorization": f"Bearer {token}"}

    with client.stream("POST", f"/v1/conv/conversations/{conversation_id}/messages", json={"text": "I like cats"}, headers=headers) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        lines = [line for line in response.iter_lines() if line.startswith("data: ")]
    assert any('"delta"' in line for line in lines)
    assert lines[-1] == 'data: {"done": true, "plan_finished": false}'

    kept = client.get(f"/v1/conv/conversations/{conversation_id}/messages", headers=headers).json()
    assert [m["role"] for m in kept] == ["user", "assistant"]
    assert kept[0]["content"] == "I like cats"


def test_a_token_works_only_for_its_own_conversation(client):
    student_id = _ready_student(client, "conv-scope")
    first_id, first_token = _open(client, _prompt_token(client, student_id))
    second_id, _ = _open(client, _prompt_token(client, student_id))
    response = client.post(
        f"/v1/conv/conversations/{second_id}/messages",
        json={"text": "hello"},
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert response.status_code == 401


def test_ending_stops_new_turns(client):
    student_id = _ready_student(client, "conv-end")
    conversation_id, token = _open(client, _prompt_token(client, student_id))
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post(f"/v1/conv/conversations/{conversation_id}/end", headers=headers).json()["status"] == "ended"
    late = client.post(f"/v1/conv/conversations/{conversation_id}/messages", json={"text": "still there?"}, headers=headers)
    assert late.status_code == 409


def test_prompt_lifetime_is_a_setting_with_limits(client):
    with SessionLocal() as db:
        set_setting(db, PROMPT_TOKEN_TTL_KEY, "120")
        assert service.prompt_ttl_seconds(db) == 120
        set_setting(db, PROMPT_TOKEN_TTL_KEY, "5")
        assert service.prompt_ttl_seconds(db) == 60
        set_setting(db, PROMPT_TOKEN_TTL_KEY, "not a number")
        assert service.prompt_ttl_seconds(db) == 3600
        set_setting(db, PROMPT_TOKEN_TTL_KEY, "3600")


def test_expired_conversations_are_removed(client):
    student_id = _ready_student(client, "conv-purge")
    conversation_id, token = _open(client, _prompt_token(client, student_id))
    client.post(
        f"/v1/conv/conversations/{conversation_id}/messages",
        json={"text": "hi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        conversation.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
        removed = service.purge_expired(db)
        assert removed >= 1
        assert db.query(Conversation).filter(Conversation.id == conversation_id).count() == 0
        assert db.query(ConvMessage).filter(ConvMessage.conversation_id == conversation_id).count() == 0


def test_api_page_is_shown_in_development(client):
    # The tests run in development, so the interactive API page is available here.
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
