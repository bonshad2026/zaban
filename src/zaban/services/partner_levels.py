# Level changes after a lesson (docs/conversation-partner.md, section 5.3). Each criterion moves on its own.
from sqlalchemy.orm import Session as DBSession

from zaban.models import Student, TutorSession
from zaban.services.partner_policy import LEVEL_CODES
from zaban.services.partner_settings import partner_value

# The summary's criterion names and the student columns that hold their levels (section 6.2).
CRITERION_COLUMNS = {
    "range": "level_range",
    "accuracy": "level_accuracy",
    "fluency": "level_fluency",
    "interaction": "level_interaction",
    "coherence": "level_coherence",
}


def next_level(current: str, recent: list[str], up: int, down: int) -> str:
    # recent holds the levels the summaries gave, newest first, and starts with the lesson that just ended.
    # Up: the last `up` lessons were all above the current level. Down: the last `down` were all below it.
    position = LEVEL_CODES.index(current)
    ranks = [LEVEL_CODES.index(level) for level in recent]
    if len(ranks) >= up and all(rank > position for rank in ranks[:up]):
        return LEVEL_CODES[min(position + 1, len(LEVEL_CODES) - 1)]
    if len(ranks) >= down and all(rank < position for rank in ranks[:down]):
        return LEVEL_CODES[max(position - 1, 0)]
    return current


def apply_criteria(db: DBSession, student: Student, session: TutorSession, criteria: dict[str, str]) -> dict[str, tuple[str, str]]:
    # Writes the lesson's levels on the session, moves each criterion of the learner if the rule says so,
    # and returns the changes as {criterion: (old, new)}. The caller commits.
    up = int(partner_value(db, "partner_level_up_sessions"))
    down = int(partner_value(db, "partner_level_down_sessions"))
    history = (
        db.query(TutorSession)
        .filter(TutorSession.student_id == student.id, TutorSession.end_status == "evaluated", TutorSession.id != session.id)
        .order_by(TutorSession.ended_at.desc())
        .limit(max(up, down))
        .all()
    )
    changes: dict[str, tuple[str, str]] = {}
    for key, column in CRITERION_COLUMNS.items():
        setattr(session, f"eval_{key}", criteria[key])
        recent = [criteria[key]] + [getattr(row, f"eval_{key}") for row in history if getattr(row, f"eval_{key}")]
        current = getattr(student, column) or "A1"
        new = next_level(current, recent, up, down)
        if new != current:
            setattr(student, column, new)
            changes[key] = (current, new)
    return changes
