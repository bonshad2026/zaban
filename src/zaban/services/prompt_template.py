import re

from sqlalchemy.orm import Session as DBSession

from zaban.models import LearnerDetails, Student, TutorProfile
from zaban.services.learner import get_accent, get_global_prompt
from zaban.services.learner_details import details_out
from zaban.services.settings_store import get_setting, set_setting

# The administrator writes a template once. The prompt is then built by filling its placeholders with stored values.
# No AI is involved: the same template and the same learner always give the same text.
TEMPLATE_KEY = "prompt_template"

DEFAULT_TEMPLATE = """[پرامپت کلی]
{{general}}

[اطلاعات دانش‌آموز]
نام: {{learner.name}}
سن: {{learner.age}}
جنسیت: {{learner.gender}}
سطح انگلیسی: {{learner.level}}
لهجه‌ی تمرین: {{learner.accent}}
کلاس یا پایه: {{learner.grade}}
سبک گفتگوی مورد علاقه: {{learner.conversation_style}}
سبک پاسخ معلم: {{learner.response_style}}
ویژگی‌ها و چیزهایی که دوست دارد: {{learner.attributes}}
علاقه‌ها: {{learner.interests}}
انگیزه: {{learner.motivation}}
نمونه‌ی انگلیسی دانش‌آموز: {{learner.level_sample}}
یادداشت مدیر: {{learner.instructions}}

[پرامپت شخصی]
{{personal_text}}
"""

# What the administrator sees for each placeholder, in the order they are offered.
PLACEHOLDERS = [
    ("general", "پرامپت کلی سامانه"),
    ("learner.name", "نام دانش‌آموز"),
    ("learner.age", "سن"),
    ("learner.gender", "جنسیت"),
    ("learner.level", "سطح انگلیسی"),
    ("learner.accent", "لهجه‌ی تمرین"),
    ("learner.grade", "کلاس یا پایه"),
    ("learner.conversation_style", "سبک گفتگوی مورد علاقه"),
    ("learner.response_style", "سبک پاسخ معلم"),
    ("learner.attributes", "ویژگی‌ها و آنچه دوست دارد معلم داشته باشد"),
    ("learner.interests", "علاقه‌ها"),
    ("learner.motivation", "انگیزه"),
    ("learner.level_sample", "نمونه‌ی انگلیسی دانش‌آموز"),
    ("learner.instructions", "یادداشت مدیر"),
    ("personal_text", "پرامپت شخصی (هرچه معلم باید بداند)"),
    ("duration", "مدت کلاس"),
]

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


def get_template(db: DBSession) -> str:
    return get_setting(db, TEMPLATE_KEY, DEFAULT_TEMPLATE)


def save_template(db: DBSession, text: str) -> None:
    set_setting(db, TEMPLATE_KEY, text)
    db.commit()


def has_saved_template(db: DBSession) -> bool:
    # Until the administrator saves a template, lessons keep the automatic prompt.
    return bool(get_setting(db, TEMPLATE_KEY))


def learner_values(db: DBSession, student: Student, duration_minutes: int = 0) -> dict[str, str]:
    # Every value is text. Empty means the information is not stored yet.
    details = details_out(db.get(LearnerDetails, student.id))
    profile = db.get(TutorProfile, student.id)
    return {
        "duration": f"{duration_minutes} دقیقه" if duration_minutes else "",
        "general": get_global_prompt(db),
        "personal_text": details["free_text"] or "",
        "learner.name": student.display_name or "",
        "learner.age": "" if details["age"] is None else str(details["age"]),
        "learner.gender": GENDER_FA.get(details["gender"] or "", ""),
        "learner.level": (
            f"شنیداری {student.level_listening or 'A1'}، خواندن {student.level_reading or 'A1'}، "
            f"دستور و واژگان {student.level_grammar or 'A1'}، گفتار و نوشتار {student.level_speaking_writing or 'A1'}"
        ),
        "learner.accent": get_accent(db, student.id),
        "learner.grade": details["grade"] or "",
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
    unknown: list[str] = []

    def fill(match: re.Match) -> str:
        key = match.group(1)
        if key not in values:
            if key not in unknown:
                unknown.append(key)
            return ""
        return values[key]

    return PLACEHOLDER_PATTERN.sub(fill, template), unknown
