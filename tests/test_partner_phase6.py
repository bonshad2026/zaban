# Phase 6 of the conversation partner (docs/conversation-partner.md, section 15.9): the remaining modes and the content library.
import os
import uuid

import pytest

from zaban.db import SessionLocal
from zaban.models import ContentItem, Student, Tenant, new_id
from zaban.services import partner_prompt
from zaban.services.content_library import active_item, add_item, validate_item
from zaban.services.partner_prompt import MODE_SPECS, mode_part
from zaban.services.partner_rhythm import MODE_LABELS, validate_rhythm
from zaban.services.partner_settings import RHYTHM_MODES

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
NEW_MODES = ["task", "functions", "phrases", "casual", "listening", "story", "poetry", "repeat"]


def _student(db, level: str = "A1") -> Student:
    tenant = db.query(Tenant).first()
    student = Student(id=new_id(), tenant_id=tenant.id, external_user_id=uuid.uuid4().hex, display_name="content", level_range=level)
    db.add(student)
    db.flush()
    return student


def _item(db, kind: str, level: str, text: str) -> ContentItem:
    item = add_item(db, kind, level, f"title {uuid.uuid4().hex[:6]}", text, "made by the system", "system")
    db.commit()
    return item


def _remove(db, *items: ContentItem) -> None:
    for item in items:
        db.delete(item)
    db.commit()


def test_every_rhythm_mode_has_a_label_and_a_text():
    assert set(RHYTHM_MODES) <= set(MODE_SPECS)
    assert set(RHYTHM_MODES) <= set(MODE_LABELS)
    for mode in NEW_MODES:
        assert mode in RHYTHM_MODES


def test_a_lesson_rhythm_can_use_the_new_modes():
    parts = validate_rhythm([{"mode": "story", "minutes": 6}, {"mode": "repeat", "minutes": 4}, {"mode": "task", "minutes": 5}], 20)
    assert [p["mode"] for p in parts] == ["story", "repeat", "task"]


def test_story_length_follows_the_range_level(client):
    with SessionLocal() as db:
        student = _student(db, "B1")
        text = mode_part(db, "story", student=student).text
    assert "12 to 20 sentences" in text


def test_modes_without_content_add_no_length_line(client):
    with SessionLocal() as db:
        student = _student(db, "B1")
        assert "Length:" not in mode_part(db, "phrases", student=student).text


def test_content_needs_a_source_and_a_licence(client):
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            validate_item("story", "A1", "t", "text", "", "public domain")
        with pytest.raises(ValueError):
            validate_item("story", "A1", "t", "text", "some book", " ")
        with pytest.raises(ValueError):
            validate_item("novel", "A1", "t", "text", "some book", "public domain")
        with pytest.raises(ValueError):
            validate_item("story", "Z9", "t", "text", "some book", "public domain")


def test_the_newest_active_text_of_the_level_is_used(client):
    marker_old = f"OLD-STORY-{uuid.uuid4().hex[:6]}"
    marker_new = f"NEW-STORY-{uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        student = _student(db, "A2")
        old = _item(db, "story", "A1", marker_old)
        new = _item(db, "story", "A2", marker_new)
        too_hard = _item(db, "story", "C1", "HARD-STORY-" + uuid.uuid4().hex[:6])
        chosen = active_item(db, "story", student)
        assert chosen.id == new.id
        new.active = False
        db.commit()
        assert active_item(db, "story", student).id == old.id
        text = mode_part(db, "story", student=student).text
        assert marker_old in text and marker_new not in text
        _remove(db, old, new, too_hard)


def test_admin_adds_and_switches_off_a_text(client):
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    payload = {"kind": "poem", "level": "A2", "title": "A short poem", "text": "Line one\nLine two", "source": "public domain collection", "licence": "public domain"}
    assert client.post("/v1/admin/api/content", json={**payload, "licence": ""}).status_code in (400, 422)
    created = client.post("/v1/admin/api/content", json=payload)
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]
    listed = client.get("/v1/admin/api/content").json()
    assert any(row["id"] == item_id and row["active"] is True for row in listed)
    assert client.post(f"/v1/admin/api/content/{item_id}/active", json={"active": False}).status_code == 200
    listed = client.get("/v1/admin/api/content").json()
    assert any(row["id"] == item_id and row["active"] is False for row in listed)
    with SessionLocal() as db:
        db.query(ContentItem).filter_by(id=item_id).delete()
        db.commit()


def test_partner_prompt_module_has_no_child_wording(client):
    with SessionLocal() as db:
        student = _student(db)
        text = " ".join(mode_part(db, mode, student=student).text for mode in NEW_MODES).lower()
    assert "child" not in text and "grade" not in text
    assert partner_prompt.PASSAGE_SENTENCES["A1"] == "5 to 8"
