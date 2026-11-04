from sqlalchemy.orm import Session as DBSession

from zaban.models import AppSetting, LearnerPreference, TutorProfile
from zaban.services.accents import ACCENTS, DEFAULT_ACCENT

GLOBAL_PROMPT_KEY = "global_prompt"


def get_accent(db: DBSession, student_id: str) -> str:
    row = db.get(LearnerPreference, student_id)
    return row.accent if row else DEFAULT_ACCENT


def set_accent(db: DBSession, student_id: str, accent: str) -> None:
    if accent not in ACCENTS:
        raise ValueError("unknown accent")
    row = db.get(LearnerPreference, student_id)
    if row is None:
        db.add(LearnerPreference(student_id=student_id, accent=accent))
    else:
        row.accent = accent


def get_global_prompt(db: DBSession) -> str:
    row = db.get(AppSetting, GLOBAL_PROMPT_KEY)
    return row.value if row else ""


def set_global_prompt(db: DBSession, text: str) -> None:
    row = db.get(AppSetting, GLOBAL_PROMPT_KEY)
    if row is None:
        db.add(AppSetting(key=GLOBAL_PROMPT_KEY, value=text))
    else:
        row.value = text


# Only the fields that are passed (not None) change, so a partial update keeps the rest.
def set_learner_profile(
    db: DBSession,
    student_id: str,
    *,
    interests: str | None = None,
    motivation: str | None = None,
    instructions: str | None = None,
) -> None:
    profile = db.get(TutorProfile, student_id)
    if profile is None:
        profile = TutorProfile(student_id=student_id)
        db.add(profile)
    if interests is not None:
        profile.interests = interests.strip()
    if motivation is not None:
        profile.motivation = motivation.strip()
    if instructions is not None:
        profile.instructions = instructions.strip()
