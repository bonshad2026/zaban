# Phase 5 of the conversation partner (docs/conversation-partner.md, section 15.8), browser-only version.
# Speech is turned into text in the browser; the server never receives audio. Shadowing and pronunciation are modes of the lesson rhythm.
import pytest

from zaban.db import SessionLocal
from zaban.services import partner_prompt
from zaban.services.partner_output import MODES, parse_output
from zaban.services.partner_rhythm import MODE_LABELS, validate_rhythm
from zaban.services.partner_settings import RHYTHM_MODES, normalize, SPEC_BY_KEY


def test_shadowing_and_pronunciation_are_rhythm_modes_with_labels():
    assert "shadowing" in RHYTHM_MODES and "pronunciation" in RHYTHM_MODES
    assert MODE_LABELS["shadowing"] == "شادوینگ" and MODE_LABELS["pronunciation"] == "تلفظ و آهنگ"


def test_the_default_rhythm_setting_accepts_the_new_modes():
    spec = SPEC_BY_KEY["partner_default_rhythm"]
    assert normalize(spec, "conversation:50,shadowing:30,pronunciation:20") == "conversation:50,shadowing:30,pronunciation:20"


def test_a_lesson_rhythm_can_hold_the_new_modes():
    parts = validate_rhythm([{"mode": "shadowing", "minutes": 5}, {"mode": "pronunciation", "minutes": 5}], 20)
    assert [p["mode"] for p in parts] == ["shadowing", "pronunciation"]


def test_the_contract_accepts_the_new_mode_names():
    turn = parse_output('{"mode": "shadowing", "reply": "Say: I like tea.", "feedback": null, "new_phrase": null, "next_action": "continue"}')
    assert turn.valid and turn.mode == "shadowing"
    assert "shadowing" in MODES and "pronunciation" in MODES


@pytest.mark.parametrize("mode", ["shadowing", "pronunciation"])
def test_each_new_mode_says_it_only_sees_words(client, mode):
    with SessionLocal() as db:
        text = partner_prompt.mode_part(db, mode).text
    assert "word" in text.lower()


def test_the_server_has_no_audio_upload_route(client):
    # Speech stays in the browser. If an audio route is ever added, this test reminds us to review the privacy choice first.
    from zaban.main import app

    paths = [getattr(route, "path", "") for route in app.routes]
    assert not [path for path in paths if "audio" in path.lower()]
