import os
import uuid

from zaban.curriculum_data import TOPICS
from zaban.db import SessionLocal
from zaban.models import CurriculumTopic, Student, Tenant, TutorSession, utcnow
from zaban.services.curriculum import choose_topic, record_lesson_topic, session_topic, topic_note, variant_for
from zaban.services.sessions import build_system_prompt

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def _new_student(age_band: str, level: str) -> str:
    with SessionLocal() as db:
        tenant = db.query(Tenant).first()
        student = Student(
            tenant_id=tenant.id,
            external_user_id=f"curr-{uuid.uuid4().hex}",
            display_name="Curriculum test",
            age_band=age_band,
            cefr_level=level,
        )
        db.add(student)
        db.commit()
        return student.id


def test_curriculum_needs_admin_sign_in(client):
    assert client.get("/v1/admin/api/curriculum").status_code == 401


def test_catalog_is_seeded_with_every_topic_and_the_written_versions(client):
    _admin(client)
    catalog = client.get("/v1/admin/api/curriculum").json()

    assert len(catalog["topics"]) == len(TOPICS)
    assert catalog["levels"] == ["A1", "A2", "B1", "B2", "C1", "C2"]
    intro = next(t for t in catalog["topics"] if t["id"] == "INTRO")
    written = {slot["variant_id"] for slot in intro["slots"] if slot["written"]}
    assert {"INTRO.K.A1", "INTRO.J.A1", "INTRO.T.A2", "INTRO.S.B1", "INTRO.A.B2", "INTRO.A.C1", "INTRO.A.C2"} <= written
    assert any(v["id"] == "INTRO.A.C2" for v in catalog["variants"])


def test_a_saved_variant_bumps_the_version_and_reaches_the_prompt(client):
    _admin(client)
    before = client.get("/v1/admin/api/curriculum").json()["version"]
    original = next(v for v in client.get("/v1/admin/api/curriculum").json()["variants"] if v["id"] == "INTRO.J.A1")

    saved = client.put(
        "/v1/admin/api/curriculum/variants/INTRO.J.A1",
        json={"opener": "Hello there, friend!", "phrases": ["I'm…", "  ", "I like…"], "style": "test style"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == before + 1

    with SessionLocal() as db:
        topic = db.get(CurriculumTopic, "INTRO")
        variant = variant_for(db, "INTRO", "J", "A1")
        note = topic_note(topic, variant)
        assert variant.phrases == ["I'm…", "I like…"]
    assert "Hello there, friend!" in note
    assert "Version for this learner: INTRO.J.A1" in note

    restored = client.put(
        "/v1/admin/api/curriculum/variants/INTRO.J.A1",
        json={"opener": original["opener"], "phrases": original["phrases"], "style": original["style"]},
    )
    assert restored.status_code == 200


def test_a_new_version_must_fit_the_topic(client):
    _admin(client)
    outside = client.post(
        "/v1/admin/api/curriculum/variants",
        json={"topic_id": "NEWS_EVENTS", "band": "K", "level": "B1", "opener": "x", "phrases": [], "style": ""},
    )
    assert outside.status_code == 400

    duplicate = client.post(
        "/v1/admin/api/curriculum/variants",
        json={"topic_id": "INTRO", "band": "A", "level": "B2", "opener": "x", "phrases": [], "style": ""},
    )
    assert duplicate.status_code == 409

    created = client.post(
        "/v1/admin/api/curriculum/variants",
        json={"topic_id": "PETS", "band": "K", "level": "A1", "opener": "I have a pet.", "phrases": ["I have a…"], "style": "picture game"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["id"] == "PETS.K.A1"


def test_topic_choice_respects_age_band_and_level(client):
    student_id = _new_student("11-14", "A2")
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        topic, variant = choose_topic(db, student)
        assert (topic.id, variant.id) == ("INTRO", "INTRO.T.A2")

        assert choose_topic(db, student, "NEWS_EVENTS") is None  # adults and teens only
        assert choose_topic(db, student, "INTRO")[1].id == "INTRO.T.A2"


def test_recently_used_topics_are_skipped_when_another_fits(client):
    student_id = _new_student("4-6", "A1")
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        first_topic, first_variant = choose_topic(db, student)
        assert first_topic.id == "INTRO"

        now = utcnow()
        lesson = TutorSession(student_id=student_id, duration_minutes=15, started_at=now, ends_at=now)
        db.add(lesson)
        db.flush()
        record_lesson_topic(db, lesson.id, first_topic, first_variant)
        db.commit()

        # A topic used in a recent lesson comes after one that is new to this learner.
        assert choose_topic(db, student)[0].id != "INTRO"
        recorded = session_topic(db, lesson.id)
        assert recorded[0].id == "INTRO" and recorded[1].id == "INTRO.K.A1"


def test_lesson_prompt_includes_the_topic_note():
    student_id = _new_student("15-18", "B1")
    with SessionLocal() as db:
        student = db.get(Student, student_id)
        topic, variant = choose_topic(db, student)
        prompt = build_system_prompt(student, None, "main_practice", 30, "", None, "en-US", topic_note(topic, variant))
    assert "Today's topic: معرفی خود" in prompt
    assert "INTRO.S.B1" in prompt
