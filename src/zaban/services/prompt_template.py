import re

from sqlalchemy.orm import Session as DBSession

from zaban.models import LearnerDetails, Student, TutorProfile
from zaban.services.learner import get_accent, get_global_prompt
from zaban.services.learner_details import details_out
from zaban.services.skill_levels import speaking_level
from zaban.services.curriculum import next_topic

# The administrator writes a template once. The prompt is then built by filling its placeholders with stored values.
# No AI is involved: the same template and the same learner always give the same text.
GENDER_FA = {"female": "زن", "male": "مرد", "other": "سایر"}
STYLE_FA = {
    "chat": "گفتگوی آزاد",
    "story": "داستان",
    "role_play": "نقش‌بازی",
    "quiz": "پرسش و پاسخ",
    "mixed": "ترکیبی",
    "gentle": "مهربان",
    "direct": "مستقیم",
    "playful": "بازیگوش",
    "strict": "سخت‌گیر",
}

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-z_.]+)\s*\}\}")


def learner_values(db: DBSession, student: Student, duration_minutes: int = 0) -> dict[str, str]:
    # Every value is text. Empty means the information is not stored yet.
    details = details_out(db.get(LearnerDetails, student.id))
    profile = db.get(TutorProfile, student.id)
    upcoming = next_topic(db, student)
    return {
        "lesson.number": str(upcoming[0]) if upcoming else "",
        "lesson.title": upcoming[2].title if upcoming else "",
        "lesson.topic": upcoming[2].goal if upcoming else "",
        "duration": f"{duration_minutes} دقیقه" if duration_minutes else "",
        "general": get_global_prompt(db),
        "personal_text": details["free_text"] or "",
        "learner.name": student.display_name or "",
        "learner.age": "" if details["age"] is None else str(details["age"]),
        "learner.gender": GENDER_FA.get(details["gender"] or "", ""),
        "learner.level": (
            f"شنیداری {student.level_listening or 'A1'}، خواندن {student.level_reading or 'A1'}، "
            f"دستور و واژگان {student.level_grammar or 'A1'}، نوشتاری {student.level_writing or 'A1'}، "
            f"گفتاری {speaking_level(student)}"
        ),
        "learner.accent": get_accent(db, student.id),
        "learner.level_listening": student.level_listening or "",
        "learner.level_reading": student.level_reading or "",
        "learner.level_grammar": student.level_grammar or "",
        "learner.level_writing": student.level_writing or "",
        "learner.level_speaking": speaking_level(student),
        # Kept for prompt templates saved before the writing level existed.
        "learner.level_speaking_writing": speaking_level(student),
        "learner.conversation_style": STYLE_FA.get(details["conversation_style"] or "", ""),
        "learner.response_style": STYLE_FA.get(details["response_style"] or "", ""),
        "learner.attributes": details["attributes"] or "",
        "learner.interests": profile.interests if profile else "",
        "learner.motivation": profile.motivation if profile else "",
        "learner.level_sample": details["level_sample"] or "",
        "learner.instructions": profile.instructions if profile else "",
    }


def render(template: str, values: dict[str, str]) -> tuple[str, list[str]]:
    # Fills every placeholder. Returns the text and the placeholder names that the values do not know.
    # A line whose placeholders are all empty is left out, so the prompt only says what is known about the learner.
    unknown: list[str] = []
    kept: list[str] = []
    for line in template.split("\n"):
        keys = PLACEHOLDER_PATTERN.findall(line)
        for key in keys:
            if key not in values and key not in unknown:
                unknown.append(key)
        if keys and all(not values.get(key, "") for key in keys):
            continue

        def fill(match: re.Match) -> str:
            return values.get(match.group(1), "")

        kept.append(PLACEHOLDER_PATTERN.sub(fill, line))
    return "\n".join(kept), unknown
