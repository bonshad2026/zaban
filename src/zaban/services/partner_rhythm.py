# The rhythm of a lesson (docs/conversation-partner.md, section 4.15): an ordered list of parts, each with its time.
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session as DBSession

from zaban.models import TutorSession
from zaban.services.partner_settings import RHYTHM_MODES, partner_value

MAX_PARTS = 8
MODE_LABELS = {
    "conversation": "گفتگو",
    "translation": "ترجمه‌ی ذهنی",
    "review": "مرور عبارت‌ها",
    "summary": "جمع‌بندی",
    "shadowing": "شادوینگ",
    "pronunciation": "تلفظ و آهنگ",
    "task": "گفتگوی هدف‌دار",
    "functions": "کارکردهای گفتاری",
    "phrases": "عبارت‌ها و اصطلاحات",
    "casual": "محاوره‌ای کردن",
    "listening": "شنیدن",
    "story": "داستان کوتاه",
    "poetry": "شعر و ریتم",
    "repeat": "تکرار زمان‌دار",
}


def _percent_pairs(text: str) -> list[tuple[str, int]]:
    pairs = []
    for part in text.split(","):
        mode, _, percent = part.strip().partition(":")
        pairs.append((mode.strip(), int(percent)))
    return pairs


def split_minutes(text: str, duration: int) -> list[dict]:
    # Turns the percentages of the default rhythm into whole minutes that add up to the lesson length.
    pairs = [(mode, percent) for mode, percent in _percent_pairs(text) if percent > 0]
    minutes = [max(1, round(duration * percent / 100)) for _, percent in pairs]
    # The rounding difference goes to the longest part, so the total is exact.
    difference = duration - sum(minutes)
    longest = max(range(len(minutes)), key=lambda i: minutes[i])
    minutes[longest] += difference
    return [{"mode": mode, "minutes": value} for (mode, _), value in zip(pairs, minutes) if value > 0]


def start_rhythm(db: DBSession, session: TutorSession, now: datetime) -> None:
    # Called once, when a lesson of the new engine starts.
    rhythm = split_minutes(partner_value(db, "partner_default_rhythm"), session.duration_minutes)
    session.rhythm = json.dumps(rhythm)
    session.mode_index = 0
    session.mode_started_at = now


def read_rhythm(session: TutorSession) -> list[dict]:
    return json.loads(session.rhythm) if session.rhythm else []


def validate_rhythm(parts: list[dict], duration: int) -> list[dict]:
    # Checks a rhythm the learner or the administrator wants. Raises ValueError with a short reason.
    if not parts or len(parts) > MAX_PARTS:
        raise ValueError(f"a rhythm needs between 1 and {MAX_PARTS} parts")
    cleaned = []
    for part in parts:
        mode, minutes = part.get("mode"), part.get("minutes")
        if mode not in RHYTHM_MODES:
            raise ValueError(f"the mode must be one of {', '.join(RHYTHM_MODES)}")
        if not isinstance(minutes, int) or not 1 <= minutes <= duration:
            raise ValueError("each part needs whole minutes from 1 to the lesson length")
        cleaned.append({"mode": mode, "minutes": minutes})
    if sum(part["minutes"] for part in cleaned) > duration:
        raise ValueError("the parts are longer than the lesson")
    return cleaned


def segment_state(session: TutorSession, now: datetime) -> dict:
    # What the lesson page shows: the running part, the time left in it, and the part after it.
    rhythm = read_rhythm(session)
    if not rhythm or session.mode_started_at is None:
        return {"mode": "conversation", "label": MODE_LABELS["conversation"], "seconds_left": None, "over": False, "next_mode": None, "parts": []}
    index = min(session.mode_index, len(rhythm) - 1)
    part = rhythm[index]
    ends = session.mode_started_at + timedelta(minutes=part["minutes"])
    seconds_left = max(0, int((ends - now).total_seconds()))
    following = rhythm[index + 1]["mode"] if index + 1 < len(rhythm) else None
    return {
        "mode": part["mode"],
        "label": MODE_LABELS[part["mode"]],
        "seconds_left": seconds_left,
        "over": seconds_left == 0,
        "next_mode": following,
        "parts": rhythm,
        "index": index,
    }


def move(session: TutorSession, now: datetime, to: str) -> None:
    # "current" keeps the part and starts its time again, "next" goes to the part after it, or a mode name jumps to its part.
    rhythm = read_rhythm(session)
    if not rhythm:
        raise ValueError("this lesson has no rhythm")
    if to == "current":
        index = min(session.mode_index, len(rhythm) - 1)
    elif to == "next":
        if session.mode_index + 1 >= len(rhythm):
            raise ValueError("there is no next part")
        index = session.mode_index + 1
    else:
        matches = [i for i, part in enumerate(rhythm) if part["mode"] == to]
        if not matches:
            raise ValueError("that part is not in this lesson's rhythm")
        index = matches[0]
    session.mode_index = index
    session.mode_started_at = now


def set_rhythm(session: TutorSession, now: datetime, parts: list[dict]) -> None:
    # The learner changes the order, the count or the time of the parts. The first part starts again.
    cleaned = validate_rhythm(parts, session.duration_minutes)
    session.rhythm = json.dumps(cleaned)
    session.mode_index = 0
    session.mode_started_at = now
