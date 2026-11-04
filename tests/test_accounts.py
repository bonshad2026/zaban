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
