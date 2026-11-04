import os

from fastapi.testclient import TestClient

from zaban.main import app

DEMO = {"X-API-Key": os.environ["ZABAN_DEMO_API_KEY"]}
STUDENT_USERNAME = os.environ["ZABAN_DEMO_STUDENT_USERNAME"]
STUDENT_PASSWORD = os.environ["ZABAN_DEMO_STUDENT_PASSWORD"]


def test_a_new_learner_sign_in_ends_the_older_one(client):
    first = TestClient(app)
    second = TestClient(app)
    assert first.post("/v1/web/student/login", json={"username": STUDENT_USERNAME, "password": STUDENT_PASSWORD}).status_code == 200
    assert first.get("/v1/web/me?role=student").status_code == 200

    assert second.post("/v1/web/student/login", json={"username": STUDENT_USERNAME, "password": STUDENT_PASSWORD}).status_code == 200

    assert first.get("/v1/web/me?role=student").status_code == 401
    assert second.get("/v1/web/me?role=student").status_code == 200


def test_placement_accepts_a_level_picked_by_a_parent(client):
    created = client.post("/v1/students", headers=DEMO, json={"age_band": "11-14", "display_name": "Level Kid"})
    student_id = created.json()["id"]

    placed = client.post(f"/v1/students/{student_id}/placement", headers=DEMO, json={"level": "B1"})
    assert placed.status_code == 200, placed.text
    assert placed.json()["cefr_level"] == "B1"


def test_placement_needs_exactly_one_of_level_or_score(client):
    created = client.post("/v1/students", headers=DEMO, json={"age_band": "11-14", "display_name": "Both"})
    student_id = created.json()["id"]

    assert client.post(f"/v1/students/{student_id}/placement", headers=DEMO, json={}).status_code == 422
    assert client.post(
        f"/v1/students/{student_id}/placement", headers=DEMO, json={"level": "A1", "score": 10}
    ).status_code == 422


def test_learner_level_test_sets_the_level_once(client):
    created = client.post(
        "/v1/students",
        headers=DEMO,
        json={"age_band": "11-14", "display_name": "Quiz Kid", "username": "quiz-kid-1", "password": "4444"},
    )
    assert created.status_code == 201, created.text
    learner = TestClient(app)
    assert learner.post("/v1/web/student/login", json={"username": "quiz-kid-1", "password": "4444"}).status_code == 200

    questions = learner.get("/v1/web/student/level-test").json()
    assert len(questions) == 6 and "answer" not in questions[0]

    # Every answer correct gives C1; the level then cannot be changed by the learner.
    right = [0, 1, 2, 0, 0, 0]
    done = learner.post("/v1/web/student/level-test", json={"answers": right})
    assert done.status_code == 200, done.text
    assert done.json() == {"score": 6, "total": 6, "level": "C1"}
    assert learner.post("/v1/web/student/level-test", json={"answers": right}).status_code == 409


def test_level_test_needs_a_learner_sign_in(client):
    assert TestClient(app).get("/v1/web/student/level-test").status_code == 401


def test_learner_chooses_an_accent_and_the_lesson_prompt_uses_it(client):
    from zaban.db import SessionLocal
    from zaban.models import Student
    from zaban.services.learner import get_accent, set_accent
    from zaban.services.sessions import build_system_prompt

    created = client.post(
        "/v1/students",
        headers=DEMO,
        json={"age_band": "11-14", "display_name": "Accent Kid", "username": "accent-kid-1", "password": "5555"},
    )
    assert created.status_code == 201, created.text
    learner = TestClient(app)
    learner.post("/v1/web/student/login", json={"username": "accent-kid-1", "password": "5555"})

    assert learner.get("/v1/web/student/accent").json() == {"accent": "en-US"}
    assert learner.post("/v1/web/student/accent", json={"accent": "en-GB"}).status_code == 200
    assert learner.get("/v1/web/student/accent").json() == {"accent": "en-GB"}
    assert learner.post("/v1/web/student/accent", json={"accent": "fr-FR"}).status_code == 422

    student_id = created.json()["id"]
    with SessionLocal() as db:
        assert get_accent(db, student_id) == "en-GB"
        prompt = build_system_prompt(db.get(Student, student_id), None, "warm_up", 10, "", None, "en-GB")
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
        json={"age_band": "11-14", "display_name": "Sample Kid", "username": "sample-kid-1", "password": "6666"},
    )
    assert created.status_code == 201, created.text
    learner = TestClient(app)
    learner.post("/v1/web/student/login", json={"username": "sample-kid-1", "password": "6666"})
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
