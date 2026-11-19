# The level rule for the skills that a test measures with a score: listening, writing, reading and grammar (stage 2).
# A test's score (0 to 100) gives the level it shows, with the same bands as the progress page. The level moves
# by the same rule as the speaking criteria: one step up after the last few results are all above it, and one step
# down after the last few are all below it.
from sqlalchemy.orm import Session as DBSession

from zaban.models import LearnerEvaluation, Student
from zaban.services.partner_levels import next_level
from zaban.services.partner_policy import LEVEL_CODES
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


# ----- Stage 3: one level for each skill. There is no overall level. -----

CRITERION_COLUMNS = {
    "range": "level_range",
    "accuracy": "level_accuracy",
    "fluency": "level_fluency",
    "interaction": "level_interaction",
    "coherence": "level_coherence",
}


def speaking_level(student: Student) -> str:
    # The speaking level is the lowest of the five criteria, so one weak criterion is not hidden by strong ones.
    levels = [getattr(student, column) or "A1" for column in CRITERION_COLUMNS.values()]
    return min(levels, key=LEVEL_CODES.index)


def level_for_skill(student: Student, skill: str) -> str:
    # The level of a skill for a test of that skill. Speaking, mixed and unknown skills use the speaking level.
    column = SCORED_SKILL_COLUMNS.get(skill)
    if column is None:
        return speaking_level(student)
    return getattr(student, column) or "A1"


def levels_out(student: Student) -> dict:
    # The levels the learner and the administrator see: one level per skill, with the five speaking criteria.
    return {
        "listening": student.level_listening or "A1",
        "reading": student.level_reading or "A1",
        "grammar": student.level_grammar or "A1",
        "writing": student.level_writing or "A1",
        "speaking": speaking_level(student),
        "criteria": {key: getattr(student, column) or "A1" for key, column in CRITERION_COLUMNS.items()},
    }
