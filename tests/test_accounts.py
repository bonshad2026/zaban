import os

from fastapi.testclient import TestClient

from zaban.main import app
from helpers_learner import learner_login

DEMO = {"X-API-Key": os.environ["ZABAN_DEMO_API_KEY"]}


def test_learner_chooses_an_accent_and_the_lesson_prompt_uses_it(client):
    from zaban.db import SessionLocal
    from zaban.models import Student
    from zaban.services.learner import get_accent, set_accent
    from zaban.services.partner_prompt import build_prompt

    created = client.post(
        "/v1/students",
        headers=DEMO,
        json={"age_band": "adult", "display_name": "Accent Learner", "username": "accent-learner-1", "password": "5555"},
    )
    assert created.status_code == 201, created.text
    learner = TestClient(app)
    learner_login(learner)

    assert learner.get("/v1/web/student/accent").json() == {"accent": "en-US"}
    assert learner.post("/v1/web/student/accent", json={"accent": "en-GB"}).status_code == 200
    assert learner.get("/v1/web/student/accent").json() == {"accent": "en-GB"}
    assert learner.post("/v1/web/student/accent", json={"accent": "fr-FR"}).status_code == 422

    student_id = learner.get("/v1/web/me").json()["id"]
    with SessionLocal() as db:
        assert get_accent(db, student_id) == "en-GB"
        prompt = build_prompt(db, db.get(Student, student_id))
    assert "British spelling" in prompt
    set_accent  # imported for completeness of the service API


def test_admin_uploads_a_named_voice_sample_and_learner_can_play_it(client):
    import base64

    admin = TestClient(app)
    admin.post("/v1/admin/api/login", json={"password": os.environ["ADMIN_PASSWORD"]})
    audio = b"ID3" + b"\x00" * 64
    uploaded = admin.post(
        "/v1/admin/api/voice-samples",
        json={"name": "Sarah - American", "accent": "en-US", "mime": "audio/mpeg",
              "data_base64": base64.b64encode(audio).decode()},
    )
    assert uploaded.status_code == 201, uploaded.text
    sample_id = uploaded.json()["id"]

    listed = admin.get("/v1/admin/api/voice-samples").json()
    assert [s["name"] for s in listed] == ["Sarah - American"]
    assert "data" not in listed[0]

    created = client.post(
        "/v1/students",
        headers=DEMO,
        json={"age_band": "adult", "display_name": "Sample Learner", "username": "sample-learner-1", "password": "6666"},
    )
    assert created.status_code == 201, created.text
    learner = TestClient(app)
    learner_login(learner)
    assert learner.get("/v1/web/student/voice-samples").json()[0]["name"] == "Sarah - American"
    played = learner.get(f"/v1/web/student/voice-samples/{sample_id}/audio")
    assert played.status_code == 200 and played.content == audio
    assert played.headers["content-type"].startswith("audio/mpeg")

    assert admin.post(
        "/v1/admin/api/voice-samples",
        json={"name": "bad", "accent": "en-US", "mime": "audio/mpeg", "data_base64": "%%%%"},
    ).status_code == 400
    assert admin.delete(f"/v1/admin/api/voice-samples/{sample_id}").status_code == 200
    assert admin.get("/v1/admin/api/voice-samples").json() == []
