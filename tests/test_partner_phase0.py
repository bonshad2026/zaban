# Phase 0 of the conversation partner (docs/conversation-partner.md, section 15.3): tables, columns, settings and the phrase library.
import os

import pytest
from sqlalchemy import inspect

from zaban.db import SessionLocal, engine
from zaban.models import PhraseItem
from zaban.services.partner_settings import PARTNER_SETTINGS, normalize, partner_value
from zaban.services.phrase_library import add_phrase, phrase_key
from zaban.services.settings_store import get_setting, set_setting

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
NEW_TABLES = {
    "phrase_library",
    "phrase_review_queue",
    "learner_phrases",
    "learner_errors",
    "session_logs",
    "learner_memory",
    "learner_memory_versions",
}


@pytest.fixture(autouse=True)
def _restore_partner_settings():
    # Tests change the partner settings in the database. Remove the test values so other tests see the defaults.
    yield
    with SessionLocal() as db:
        for spec in PARTNER_SETTINGS:
            set_setting(db, spec["key"], "")
        db.commit()


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def test_new_tables_and_columns_exist(client):
    names = set(inspect(engine).get_table_names())
    assert NEW_TABLES <= names
    student_columns = {c["name"] for c in inspect(engine).get_columns("students")}
    assert {"level_range", "level_accuracy", "level_fluency", "level_interaction", "level_coherence", "register_pref"} <= student_columns
    session_columns = {c["name"] for c in inspect(engine).get_columns("sessions")}
    assert {"eval_range", "eval_coherence", "end_status", "session_kind"} <= session_columns


def test_phrase_key_ignores_case_and_punctuation():
    assert phrase_key("I'm particularly interested in…") == phrase_key("im particularly interested in")
    assert phrase_key("What do you  do?") == "what do you do"


def test_same_phrase_is_stored_once(client):
    with SessionLocal() as db:
        first = add_phrase(db, "Could I have a table for two?", "A2", situation="restaurant")
        db.flush()
        second = add_phrase(db, "could I have a table for two", "A2")
        db.commit()
        assert first is not None and second is None
        count = db.query(PhraseItem).filter(PhraseItem.text_key == phrase_key("could I have a table for two")).count()
        assert count == 1
        db.query(PhraseItem).filter(PhraseItem.text_key == phrase_key("could I have a table for two")).delete()
        db.commit()


def test_normalize_accepts_valid_values():
    specs = {spec["key"]: spec for spec in PARTNER_SETTINGS}
    assert normalize(specs["partner_mastery_count"], " 3 ") == "3"
    assert normalize(specs["partner_review_intervals"], "3, 7,14 ,30") == "3,7,14,30"
    assert normalize(specs["partner_translation_seconds"], "A1:20, B2:7") == "A1:20,B2:7"
    assert normalize(specs["partner_default_rhythm"], "conversation:50,translation:50") == "conversation:50,translation:50"


@pytest.mark.parametrize(
    "key, raw",
    [
        ("partner_mastery_count", "0"),
        ("partner_mastery_count", "two"),
        ("partner_review_intervals", ""),
        ("partner_review_intervals", "3,x"),
        ("partner_translation_seconds", "A9:20"),
        ("partner_translation_seconds", "A1:0"),
        ("partner_translation_seconds", "a1:20"),
        ("partner_default_rhythm", "conversation:60,translation:20"),
        ("partner_default_rhythm", "dance:100"),
    ],
)
def test_normalize_refuses_bad_values(key, raw):
    spec = next(s for s in PARTNER_SETTINGS if s["key"] == key)
    with pytest.raises(ValueError):
        normalize(spec, raw)


def test_defaults_are_used_when_nothing_is_saved():
    with SessionLocal() as db:
        assert partner_value(db, "partner_mastery_count") == "2"
        assert partner_value(db, "partner_review_intervals") == "3,7,14,30"
        assert partner_value(db, "partner_default_rhythm") == "conversation:60,translation:20,review:10,summary:10"


def test_admin_lists_settings_with_defaults(client):
    _admin(client)
    rows = client.get("/v1/admin/api/partner-settings").json()
    keys = {row["key"] for row in rows}
    assert {"partner_mastery_count", "partner_token_reserve", "partner_memory_max_words"} <= keys
    engine_row = next(row for row in rows if row["key"] == "partner_mastery_count")
    assert engine_row["value"] == "2" and engine_row["is_default"] is True


def test_admin_saves_valid_values_and_refuses_bad_ones(client):
    _admin(client)
    saved = client.post(
        "/v1/admin/api/partner-settings",
        json={"values": {"partner_mastery_count": "4", "partner_review_intervals": "2,5"}},
    )
    assert saved.status_code == 200, saved.text
    rows = {row["key"]: row for row in saved.json()}
    assert rows["partner_mastery_count"]["value"] == "4" and rows["partner_mastery_count"]["is_default"] is False
    assert rows["partner_review_intervals"]["value"] == "2,5"

    # One bad value in the same request saves nothing, not even the good one.
    refused = client.post(
        "/v1/admin/api/partner-settings",
        json={"values": {"partner_mastery_count": "99", "partner_review_intervals": "1,1"}},
    )
    assert refused.status_code == 400
    with SessionLocal() as db:
        assert partner_value(db, "partner_mastery_count") == "4"


def test_admin_refuses_unknown_setting(client):
    _admin(client)
    response = client.post("/v1/admin/api/partner-settings", json={"values": {"partner_unknown": "1"}})
    assert response.status_code == 400


def test_partner_settings_need_admin_login(client):
    response = client.get("/v1/admin/api/partner-settings")
    assert response.status_code in (401, 403)
