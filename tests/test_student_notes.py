import os

from zaban.db import SessionLocal
from zaban.models import Student
from zaban.services.sessions import build_system_prompt

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def _first_student(client) -> dict:
    students = client.get("/v1/admin/api/students").json()
    assert students, "the demo student should be seeded in development"
    return students[0]


def test_student_list_needs_admin_sign_in(client):
    assert client.get("/v1/admin/api/students").status_code == 401


def test_admin_saves_notes_and_they_reach_the_lesson_prompt(client):
    _admin(client)
    student = _first_student(client)
    note = "Likes football and drawing. Use short sentences and easy examples."

    saved = client.post(f"/v1/admin/api/students/{student['id']}/profile", json={"instructions": f"  {note}  "})
    assert saved.status_code == 200, saved.text

    row = next(s for s in client.get("/v1/admin/api/students").json() if s["id"] == student["id"])
    assert row["instructions"] == note

    with SessionLocal() as db:
        db_student = db.get(Student, student["id"])
        prompt = build_system_prompt(db_student, None, "warm_up", 45, row["instructions"])
    assert note in prompt
    assert "<notes>" in prompt
    assert "never change the rules below" in prompt


def test_empty_notes_clear_the_prompt_section(client):
    _admin(client)
    student = _first_student(client)
    client.post(f"/v1/admin/api/students/{student['id']}/profile", json={"instructions": "Likes trains."})

    assert client.post(f"/v1/admin/api/students/{student['id']}/profile", json={"instructions": "  "}).status_code == 200

    with SessionLocal() as db:
        db_student = db.get(Student, student["id"])
        prompt = build_system_prompt(db_student, None, "warm_up", 45, "")
    assert "<notes>" not in prompt


def test_notes_for_unknown_student_are_not_found(client):
    _admin(client)
    response = client.post("/v1/admin/api/students/missing/profile", json={"instructions": "Hi"})
    assert response.status_code == 404


def test_notes_are_length_limited(client):
    _admin(client)
    student = _first_student(client)
    response = client.post(
        f"/v1/admin/api/students/{student['id']}/profile", json={"instructions": "x" * 2001}
    )
    assert response.status_code == 422
