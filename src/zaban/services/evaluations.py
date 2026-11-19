# The one place that writes an evaluated activity to the learner_evaluations table.
# Lessons, free talks and self-tests all use it, so every evaluation is kept the same way.
import json

from sqlalchemy.orm import Session as DBSession

from zaban.models import LearnerEvaluation, utcnow


def record_evaluation(
    db: DBSession,
    student_id: str,
    source: str,
    source_id: str,
    skill: str,
    feedback: str | None,
    score: float | None,
    changes: dict | None,
) -> LearnerEvaluation:
    # changes maps a criterion or skill to its (old, new) level. The caller commits.
    row = LearnerEvaluation(
        student_id=student_id,
        source=source,
        source_id=source_id,
        skill=skill,
        score=score,
        feedback=feedback or "",
        changes=json.dumps({key: list(pair) for key, pair in (changes or {}).items()}, ensure_ascii=False),
        created_at=utcnow(),
    )
    db.add(row)
    return row
