# The level rule for the skills that a test measures with a score: listening, writing, reading and grammar (stage 2).
# A test's score (0 to 100) gives the level it shows, with the same bands as the progress page. The level moves
# by the same rule as the speaking criteria: one step up after the last few results are all above it, and one step
# down after the last few are all below it.
from sqlalchemy.orm import Session as DBSession

from zaban.models import LearnerEvaluation, Student
from zaban.services.partner_levels import next_level
from zaban.services.partner_settings import partner_value
from zaban.services.progress import cefr_from_score

SCORED_SKILL_COLUMNS = {
    "listening": "level_listening",
    "reading": "level_reading",
    "grammar": "level_grammar",
    "writing": "level_writing",
}


def apply_scored_skill(db: DBSession, student: Student, skill: str, score: float | None, source_id: str) -> dict:
    # Returns {skill: (old, new)} when the level moves, otherwise {}. The caller commits.
    column = SCORED_SKILL_COLUMNS.get(skill)
    if column is None or score is None:
        return {}
    up = int(partner_value(db, "partner_level_up_sessions"))
    down = int(partner_value(db, "partner_level_down_sessions"))
    history = (
        db.query(LearnerEvaluation)
        .filter(
            LearnerEvaluation.student_id == student.id,
            LearnerEvaluation.skill == skill,
            LearnerEvaluation.score.isnot(None),
            LearnerEvaluation.source_id != source_id,
        )
        .order_by(LearnerEvaluation.created_at.desc())
        .limit(max(up, down))
        .all()
    )
    recent = [cefr_from_score(round(score))] + [cefr_from_score(round(row.score)) for row in history]
    current = getattr(student, column) or "A1"
    new = next_level(current, recent, up, down)
    if new == current:
        return {}
    setattr(student, column, new)
    return {skill: (current, new)}
