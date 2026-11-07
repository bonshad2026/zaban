import os
import uuid

from zaban.db import SessionLocal
from zaban.models import LearningProgram, LessonItem, Student, StudentProgress, Tenant, TutorSession, utcnow
from zaban.services.programs import advance_if_done, ensure_progress, program_for

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
DEMO = {"X-API-Key": os.environ["ZABAN_DEMO_API_KEY"]}
PROGRAM_ID = "T-A1-daily-p1"


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def _new_student(age_band: str, level: str) -> str:
    with SessionLocal() as db:
        tenant = db.query(Tenant).first()
        student = Student(
            tenant_id=tenant.id,
            external_user_id=f"prog-{uuid.uuid4().hex}",
            display_name="Program test",
            age_band=age_band,
            cefr_level=level,
        )
        db.add(student)
        db.commit()
        return student.id


def _finish_one_lesson(db, student_id: str) -> None:
    # Simulates a lesson that was played and ended: a completed session linked to the current program item.
    now = utcnow()
    session = TutorSession(student_id=student_id, duration_minutes=10, status="completed", started_at=now, ends_at=now, ended_at=now)
    db.add(session)
    db.flush()
    progress = db.get(StudentProgress, student_id)
    db.add(LessonItem(session_id=session.id, program_id=progress.program_id, position=progress.position, program_version=1))
    db.commit()
    advance_if_done(db, student_id)
    db.commit()


def test_the_first_program_has_100_lessons_and_is_seeded(client):
    _admin(client)
    data = client.get("/v1/admin/api/programs").json()
    program = next(p for p in data["programs"] if p["id"] == PROGRAM_ID)
    assert len(program["items"]) == 100
    assert program["items"][0]["title"] == "سلام و معرفی"
    assert program["block_size"] == 24
    assert {g["key"] for g in data["goals"]} >= {"daily_conversation", "school", "travel", "work", "hobbies"}


def test_editing_a_lesson_is_saved_and_bumps_the_version(client):
    _admin(client)
    before = next(p for p in client.get("/v1/admin/api/programs").json()["programs"] if p["id"] == PROGRAM_ID)

    saved = client.put(
        f"/v1/admin/api/programs/{PROGRAM_ID}/items/2",
        json={"title": "احوال‌پرسی (ویرایش)", "activity": "بازی", "phrases": ["How are you?", "  ", "Good morning."]},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == before["version"] + 1

    after = next(p for p in client.get("/v1/admin/api/programs").json()["programs"] if p["id"] == PROGRAM_ID)
    item = after["items"][1]
    assert item["title"] == "احوال‌پرسی (ویرایش)"
    assert item["phrases"] == ["How are you?", "Good morning."]

    client.put(
        f"/v1/admin/api/programs/{PROGRAM_ID}/items/2",
        json={"title": "احوال‌پرسی", "activity": "بازی «توپ سلام»", "phrases": ["How are you?", "I'm fine, thanks."]},
    )


def test_a_program_is_chosen_by_age_level_and_goal():
    student_id = _new_student("11-14", "A1")
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        assert program_for(db, student).id == PROGRAM_ID
        assert program_for(db, _as_student(db, "4-6", "A1")).id == "K-A1-daily-p1"
        assert program_for(db, _as_student(db, "4-6", "B1")) is None  # no program for ages 4 to 6 above A1 yet
        assert program_for(db, _as_student(db, "11-14", "B2")) is None


def _as_student(db, age_band: str, level: str) -> Student:
    student = Student(
        tenant_id=db.query(Tenant).first().id,
        external_user_id=f"prog-{uuid.uuid4().hex}",
        display_name="",
        age_band=age_band,
        cefr_level=level,
    )
    db.add(student)
    db.commit()
    return student


def test_each_finished_lesson_moves_on_and_a_block_waits_for_approval():
    student_id = _new_student("11-14", "A1")
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        progress = ensure_progress(db, student)
        assert (progress.position, progress.status) == (0, "active")

        _finish_one_lesson(db, student_id)
        assert db.get(StudentProgress, student_id).position == 1

        for _ in range(23):
            _finish_one_lesson(db, student_id)
        progress = db.get(StudentProgress, student_id)
        assert (progress.position, progress.status) == (24, "waiting_approval")


def test_approval_resumes_the_block(client):
    student_id = _new_student("11-14", "A1")
    with SessionLocal() as db:
        progress = ensure_progress(db, db.get(Student, student_id))
        progress.position = 24
        progress.status = "waiting_approval"
        db.commit()

    _admin(client)
    resumed = client.post(f"/v1/admin/api/students/{student_id}/resume-program")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"
    approvals = client.get("/v1/admin/api/program-approvals").json()
    assert all(a["student_id"] != student_id for a in approvals)


def test_a_goal_outside_the_fixed_list_is_refused(client):
    response = client.post(
        "/v1/students",
        headers=DEMO,
        json={"age_band": "11-14", "username": "goal-check", "password": "1234", "goal": "anything"},
    )
    assert response.status_code == 422
