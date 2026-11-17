from sqlalchemy.orm import Session as DBSession

from zaban.models import TutorSession


def past_evaluations(db: DBSession, student_id: str, limit: int = 3) -> str:
    # The summaries the conversation partner wrote for earlier lessons. Shown to the administrator on the learner page.
    rows = (
        db.query(TutorSession)
        .filter(TutorSession.student_id == student_id, TutorSession.evaluation.isnot(None))
        .order_by(TutorSession.started_at.desc())
        .limit(limit)
        .all()
    )
    return "\n".join(f"- {r.started_at:%Y-%m-%d}: {r.evaluation}" for r in rows)
