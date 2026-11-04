import os

from zaban.db import SessionLocal
from zaban.models import Student, TutorProfile
from zaban.services.learner import get_global_prompt
from zaban.services.sessions import build_system_prompt

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
DEMO = {"X-API-Key": os.environ["ZABAN_DEMO_API_KEY"]}


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def _student_row(client, student_id: str) -> dict:
    return next(s for s in client.get("/v1/admin/api/students").json() if s["id"] == student_id)


def _prompt_for(student_id: str, global_prompt: str = "") -> str:
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        profile = db.get(TutorProfile, student_id)
        return build_system_prompt(student, None, "warm_up", 45, global_prompt, profile)


def test_student_list_needs_admin_sign_in(client):
    assert client.get("/v1/admin/api/students").status_code == 401


def test_admin_profile_reaches_the_lesson_prompt(client):
    _admin(client)
    student_id = client.get("/v1/admin/api/students").json()[0]["id"]

    saved = client.post(
        f"/v1/admin/api/students/{student_id}/profile",
        json={"interests": " football ", "motivation": "school", "instructions": "Use short sentences."},
    )
    assert saved.status_code == 200, saved.text

    row = _student_row(client, student_id)
    assert (row["interests"], row["motivation"], row["instructions"]) == ("football", "school", "Use short sentences.")

    prompt = _prompt_for(student_id)
    assert "<learner>" in prompt
    assert "Interests: football" in prompt
    assert "Why they learn English: school" in prompt
    assert "Teacher notes: Use short sentences." in prompt


def test_empty_profile_clears_the_learner_section(client):
    _admin(client)
    student_id = client.get("/v1/admin/api/students").json()[0]["id"]
    client.post(f"/v1/admin/api/students/{student_id}/profile", json={"instructions": "Likes trains."})

    assert client.post(f"/v1/admin/api/students/{student_id}/profile", json={}).status_code == 200

    assert "<learner>" not in _prompt_for(student_id)


def test_general_prompt_is_saved_and_used_in_every_lesson(client):
    _admin(client)
    assert client.post("/v1/admin/api/global-prompt", json={"text": "  Be warm and encouraging.  "}).status_code == 200
    assert client.get("/v1/admin/api/global-prompt").json() == {"text": "Be warm and encouraging."}

    with SessionLocal() as db:
        student = db.query(Student).first()
        global_prompt = get_global_prompt(db)
        prompt = build_system_prompt(student, None, "warm_up", 45, global_prompt, None)
    assert "Be warm and encouraging." in prompt
    assert "<guidance>" in prompt


def test_parent_or_api_key_can_set_interests_and_motivation_at_creation(client):
    created = client.post(
        "/v1/students",
        headers=DEMO,
        json={"age_band": "11-14", "display_name": "Sara", "interests": "drawing", "motivation": "travel"},
    )
    assert created.status_code == 201, created.text

    _admin(client)
    row = _student_row(client, created.json()["id"])
    assert (row["interests"], row["motivation"]) == ("drawing", "travel")


def test_unknown_student_profile_is_not_found(client):
    _admin(client)
    response = client.post("/v1/admin/api/students/missing/profile", json={"instructions": "Hi"})
    assert response.status_code == 404


def test_profile_and_general_prompt_lengths_are_limited(client):
    _admin(client)
    student_id = client.get("/v1/admin/api/students").json()[0]["id"]
    too_long_notes = client.post(
        f"/v1/admin/api/students/{student_id}/profile", json={"instructions": "x" * 2001}
    )
    assert too_long_notes.status_code == 422
    too_long_global = client.post("/v1/admin/api/global-prompt", json={"text": "x" * 4001})
    assert too_long_global.status_code == 422
