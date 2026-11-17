import os
import uuid

from zaban.curriculum_data import TOPICS
from zaban.db import SessionLocal
from zaban.models import CurriculumTopic, CurriculumVariant, LessonTopic, Student, Tenant, TutorSession, utcnow
from zaban.services.curriculum import (
    choose_topic,
    create_variant,
    record_lesson_topic,
    save_variant_text,
    session_topic,
    topic_note,
    variant_for,
)

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


def _ensure_text(db, topic_id: str, band: str, level: str, opener: str = "Hi!") -> str:
    # Writes a text for one topic, band and level, unless it exists. Returns its id.
    variant = variant_for(db, topic_id, band, level)
    if variant is None:
        variant = create_variant(db, topic_id, band, level)
        save_variant_text(variant, opener, ["I'm…"], "test style")
        db.commit()
    return variant.id


def _drop_texts(db, variant_ids: list[str]) -> None:
    # Removes the texts a test wrote, and the lesson records that use them.
    db.query(LessonTopic).filter(LessonTopic.variant_id.in_(variant_ids)).delete(synchronize_session=False)
    db.query(CurriculumVariant).filter(CurriculumVariant.id.in_(variant_ids)).delete(synchronize_session=False)
    db.commit()


def test_curriculum_needs_admin_sign_in(client):
    assert client.get("/v1/admin/api/curriculum").status_code == 401


def test_catalog_lists_every_topic_with_its_levels_and_slots(client):
    _admin(client)
    catalog = client.get("/v1/admin/api/curriculum").json()

    assert len(catalog["topics"]) == len(TOPICS)
    assert catalog["levels"] == ["A1", "A2", "B1", "B2", "C1", "C2"]
    intro = next(t for t in catalog["topics"] if t["id"] == "INTRO")
    assert intro["slots"] and all("variant_id" in slot for slot in intro["slots"])


def test_a_saved_variant_bumps_the_version_and_reaches_the_prompt(client):
    _admin(client)
    with SessionLocal() as db:
        _ensure_text(db, "INTRO", "A", "A1", opener="Hi, my name is…")
        original = variant_for(db, "INTRO", "A", "A1")
        original_text = (original.opener, list(original.phrases), original.style)
    before = client.get("/v1/admin/api/curriculum").json()["version"]

    try:
        saved = client.put(
            "/v1/admin/api/curriculum/variants/INTRO.A.A1",
            json={"opener": "Hello there, friend!", "phrases": ["I'm…", "  ", "I like…"], "style": "test style"},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["version"] == before + 1

        with SessionLocal() as db:
            topic = db.get(CurriculumTopic, "INTRO")
            variant = variant_for(db, "INTRO", "A", "A1")
            note = topic_note(topic, variant)
            assert variant.phrases == ["I'm…", "I like…"]
        assert "Hello there, friend!" in note
        assert "Version for this learner: INTRO.A.A1" in note
    finally:
        with SessionLocal() as db:
            variant = variant_for(db, "INTRO", "A", "A1")
            variant.opener, variant.phrases, variant.style = original_text[0], original_text[1], original_text[2]
            _drop_texts(db, ["INTRO.A.A1"])


def test_a_new_version_must_fit_the_topic(client):
    _admin(client)
    outside = client.post(
        "/v1/admin/api/curriculum/variants",
        json={"topic_id": "NEWS_EVENTS", "band": "A", "level": "A1", "opener": "x", "phrases": [], "style": ""},
    )
    assert outside.status_code == 400

    with SessionLocal() as db:
        _ensure_text(db, "INTRO", "A", "B2")
    try:
        duplicate = client.post(
            "/v1/admin/api/curriculum/variants",
            json={"topic_id": "INTRO", "band": "A", "level": "B2", "opener": "x", "phrases": [], "style": ""},
        )
        assert duplicate.status_code == 409

        created = client.post(
            "/v1/admin/api/curriculum/variants",
            json={"topic_id": "GREET", "band": "A", "level": "A1", "opener": "Hi, how are you?", "phrases": ["I'm fine, thanks."], "style": "everyday greeting"},
        )
        assert created.status_code == 201, created.text
        assert created.json()["id"] == "GREET.A.A1"
    finally:
        with SessionLocal() as db:
            _drop_texts(db, ["INTRO.A.B2", "GREET.A.A1"])


def test_the_path_is_the_same_for_every_age_and_level(client):
    # Topics do not depend on the learner's age or level. Only the text does.
    young = _new_student("adult", "A1")
    adult = _new_student("adult", "C2")
    with SessionLocal() as db:
        first_for_young = choose_topic(db, db.get(Student, young))
        first_for_adult = choose_topic(db, db.get(Student, adult))
        assert first_for_young[0].id == first_for_adult[0].id == "INTRO"
        # No text is written yet, so the lesson starts with the topic's title and goal only.
        assert first_for_young[1] is None and first_for_adult[1] is None
        assert choose_topic(db, db.get(Student, young), "NEWS_EVENTS")[0].id == "NEWS_EVENTS"
        assert choose_topic(db, db.get(Student, young), "NOT_A_TOPIC") is None


def test_a_finished_topic_is_skipped_for_the_next_lesson(client):
    student_id = _new_student("adult", "A1")
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

        assert choose_topic(db, student)[0].id != "INTRO"
        recorded = session_topic(db, lesson.id)
        assert recorded[0].id == "INTRO" and recorded[1] is None

