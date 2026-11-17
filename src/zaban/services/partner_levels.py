# Level changes after a lesson or a self-test (docs/conversation-partner.md, sections 5.3 and 14.6).
# Each criterion moves on its own.
from sqlalchemy.orm import Session as DBSession

from zaban.models import SelfTest, Student, TutorSession
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
    # Up: the last `up` evaluations were all above the current level. Down: the last `down` were all below it.
    position = LEVEL_CODES.index(current)
    ranks = [LEVEL_CODES.index(level) for level in recent]
    if len(ranks) >= up and all(rank > position for rank in ranks[:up]):
        return LEVEL_CODES[min(position + 1, len(LEVEL_CODES) - 1)]
    if len(ranks) >= down and all(rank < position for rank in ranks[:down]):
        return LEVEL_CODES[max(position - 1, 0)]
    return current


def recent_evaluations(db: DBSession, student_id: str, exclude_id: str, limit: int) -> list:
    # Lessons and self-tests that the partner has evaluated, newest first. Each row has the eval_* fields.
    lessons = (
        db.query(TutorSession)
        .filter(TutorSession.student_id == student_id, TutorSession.end_status == "evaluated", TutorSession.id != exclude_id)
        .order_by(TutorSession.ended_at.desc())
        .limit(limit)
        .all()
    )
    tests = (
        db.query(SelfTest)
        .filter(SelfTest.student_id == student_id, SelfTest.partner_status == "evaluated", SelfTest.id != exclude_id)
        .order_by(SelfTest.created_at.desc())
        .limit(limit)
        .all()
    )
    when = lambda row: (row.ended_at if isinstance(row, TutorSession) and row.ended_at else row.created_at)  # noqa: E731
    return sorted(lessons + tests, key=when, reverse=True)[:limit]


def apply_criteria(db: DBSession, student: Student, record, criteria: dict[str, str], history: list) -> dict[str, tuple[str, str]]:
    # Writes the levels on the record (a lesson or a self-test), moves each criterion of the learner if the rule says so,
    # and returns the changes as {criterion: (old, new)}. The caller commits.
    up = int(partner_value(db, "partner_level_up_sessions"))
    down = int(partner_value(db, "partner_level_down_sessions"))
    changes: dict[str, tuple[str, str]] = {}
    for key, column in CRITERION_COLUMNS.items():
        setattr(record, f"eval_{key}", criteria[key])
        recent = [criteria[key]] + [getattr(row, f"eval_{key}") for row in history if getattr(row, f"eval_{key}")]
        current = getattr(student, column) or "A1"
        new = next_level(current, recent, up, down)
        if new != current:
            setattr(student, column, new)
            changes[key] = (current, new)
    return changes
