import os

from zaban.db import SessionLocal
from zaban.models import Student, TutorProfile
from zaban.services.accents import DEFAULT_ACCENT
from zaban.services.sessions import compose_start_prompt, join_prompt
from helpers_learner import learner_login, self_student

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


class _Student:
    age_band = "11-14"
    cefr_level = "A1"


class _Profile:
    interests = "animals"
    motivation = "school"
    instructions = "short sentences"


def _parts(mode: str) -> dict:
    return compose_start_prompt(
        _Student(), None, 10, "Be patient.", _Profile(), DEFAULT_ACCENT, "Program lesson 1 of 100.",
        mode=mode, expected_output="Use the words from the last lesson.", course_note="Course: Daily.\n",
    )


def test_all_sources_are_in_the_start_prompt_in_order():
    parts = _parts("all")
    text = join_prompt(parts)
    assert text.index("Be patient.") < text.index("age band") < text.index("animals") < text.index("Program lesson 1")
    assert text.index("Program lesson 1") < text.index("Use the words") < text.index("Rules:")


def test_each_mode_uses_only_its_sources():
    assert _parts("student")["admin"] == ""
    assert "Be patient." not in join_prompt(_parts("student"))
    assert _parts("general")["database"] == "" and _parts("general")["learner"] == ""
    assert "animals" not in join_prompt(_parts("general"))
    assert "age band" in join_prompt(_parts("student_db"))


def test_admin_preview_builds_the_prompt_for_a_learner(client):
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    with SessionLocal() as db:
        student_id = self_student(db).id
    data = client.get(f"/v1/admin/api/students/{student_id}/start-prompt").json()
    assert set(data["parts"]) >= {"intro", "admin", "database", "learner", "rules"}
    assert data["prompt"].startswith("You are a friendly")
    assert "Rules:" in data["prompt"]
