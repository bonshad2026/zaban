# Reads the partner's answer in the contract of docs/conversation-partner.md, section 6.
# An answer that is not valid JSON is shown as plain text and logs nothing.
import json
from dataclasses import dataclass, field

MODES = ["conversation", "task", "shadowing", "translation", "pronunciation", "fluency", "functions", "listening", "story", "poetry", "phrases", "casual"]
ERROR_TYPES = ["tense", "word_order", "preposition", "literal_translation", "article", "register", "pronunciation"]
REGISTERS = ["formal", "neutral", "casual"]
NEXT_ACTIONS = ["continue", "switch_mode", "ask_learner", "end"]


@dataclass
class PartnerTurn:
    valid: bool
    reply: str
    mode: str | None = None
    feedback: dict | None = None  # error_type, original, better
    new_phrase: dict | None = None  # text, situation, register
    next_action: str = "continue"
    raw: str = field(default="", repr=False)


def _as_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _feedback(value: object) -> dict | None:
    # A category outside the list is not an error we can count, so no feedback is kept.
    if not isinstance(value, dict) or value.get("error_type") not in ERROR_TYPES:
        return None
    original, better = _as_text(value.get("original")), _as_text(value.get("better"))
    if original is None or better is None:
        return None
    return {"error_type": value["error_type"], "original": original, "better": better}


def _new_phrase(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    text = _as_text(value.get("text"))
    if text is None:
        return None
    register = value.get("register") if value.get("register") in REGISTERS else "neutral"
    return {"text": text, "situation": _as_text(value.get("situation")) or "", "register": register}


def read_json_object(raw: str) -> dict | None:
    # Some models wrap the JSON in a code fence. Take the outermost object.
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def parse_output(raw: str) -> PartnerTurn:
    text = (raw or "").strip()
    data = read_json_object(text)
    reply = _as_text(data.get("reply")) if data else None
    if data is None or reply is None:
        return PartnerTurn(valid=False, reply=text, raw=text)
    next_action = data.get("next_action") if data.get("next_action") in NEXT_ACTIONS else "continue"
    return PartnerTurn(
        valid=True,
        reply=reply,
        mode=data.get("mode") if data.get("mode") in MODES else None,
        feedback=_feedback(data.get("feedback")),
        new_phrase=_new_phrase(data.get("new_phrase")),
        next_action=next_action,
        raw=text,
    )
