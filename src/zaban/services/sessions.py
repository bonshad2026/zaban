import re
from datetime import datetime

from zaban.models import TutorSession

_BLOCKED_PATTERNS = [
    (re.compile(r"https?://|www\.", re.IGNORECASE), "links"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "email addresses"),
    (re.compile(r"\d{7,}"), "long numbers"),
    (
        re.compile(r"\b(password|credit card|bank|home address|phone number|hack|virus|download)\b", re.IGNORECASE),
        "private or technical topics",
    ),
]


def guard_message(text: str) -> str | None:
    for pattern, reason in _BLOCKED_PATTERNS:
        if pattern.search(text):
            return reason
    return None


def current_block(started_at: datetime, ends_at: datetime, now: datetime) -> str:
    total = (ends_at - started_at).total_seconds() or 1
    fraction = (now - started_at).total_seconds() / total
    if fraction < 0.1:
        return "warm_up"
    if fraction < 0.7:
        return "main_practice"
    if fraction < 0.9:
        return "review"
    return "wrap_up"


def finish_session(session: TutorSession, at: datetime) -> None:
    session.status = "completed"
    session.ended_at = at


def finish_if_due(session: TutorSession, now: datetime) -> None:
    if session.status == "active" and now >= session.ends_at:
        finish_session(session, session.ends_at)
