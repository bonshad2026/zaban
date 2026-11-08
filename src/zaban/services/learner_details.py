from sqlalchemy.orm import Session as DBSession

from zaban.models import LearnerDetails

CONVERSATION_STYLES = ("chat", "story", "role_play", "quiz", "mixed")
RESPONSE_STYLES = ("gentle", "direct", "playful", "strict")


def details_out(details: LearnerDetails | None) -> dict:
    if details is None:
        return {"age": None, "gender": None, "grade": None, "attributes": "", "conversation_style": None,
                "response_style": None, "level_sample": "", "free_text": ""}
    return {
        "age": details.age,
        "gender": details.gender,
        "grade": details.grade,
        "attributes": details.attributes,
        "conversation_style": details.conversation_style,
        "response_style": details.response_style,
        "level_sample": details.level_sample,
        "free_text": details.free_text,
    }


def save_details(db: DBSession, student_id: str, values: dict) -> LearnerDetails:
    # Only the fields that were sent change, so a partial update keeps the rest.
    row = db.get(LearnerDetails, student_id)
    if row is None:
        row = LearnerDetails(student_id=student_id)
        db.add(row)
    for key, value in values.items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)
    return row
