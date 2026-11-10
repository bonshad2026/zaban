import os

from fastapi.testclient import TestClient

from helpers_learner import learner_login, self_student
from zaban.db import SessionLocal
from zaban.main import app
from zaban.services.prompt_template import render

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def test_render_fills_known_placeholders_and_lists_unknown_ones():
    text, unknown = render("A {{learner.name}} B {{nope}} C {{ general }}", {"learner.name": "Sara", "general": "G"})
    assert text == "A Sara B  C G"
    assert unknown == ["nope"]


def test_admin_builds_the_prompt_from_the_template_and_the_stored_learner(client):
    learner = TestClient(app)
    learner_login(learner)
    learner.put("/v1/web/student/details", json={"age": 12, "gender": "female", "free_text": "I love drawing"})
    with SessionLocal() as db:
        student_id = self_student(db).id

    admin = TestClient(app)
    assert admin.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    saved = admin.post(
        "/v1/admin/api/prompt-template",
        json={"template": "General: {{general}}\nAge: {{learner.age}}\nGender: {{learner.gender}}\nNote: {{personal_text}}\nX: {{learner.typo}}"},
    )
    assert saved.status_code == 200

    built = admin.post("/v1/admin/api/prompt/generate", json={"student_id": student_id}).json()
    assert "Age: 12" in built["prompt"]
    assert "Gender: زن" in built["prompt"]
    assert "Note: I love drawing" in built["prompt"]
    assert built["unknown_placeholders"] == ["learner.typo"]
