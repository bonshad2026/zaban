from sqlalchemy.orm import Session as DBSession

from zaban.models import Student, Tenant, TutorSession
from zaban.services.ai_gateway import complete
from zaban.services.curriculum import next_topic
from zaban.services.metering import record_usage
from zaban.services.self_test import split_score

EVALUATION_INSTRUCTIONS = (
    "Write a short evaluation of this English lesson for the parent, in English, in at most five sentences. "
    "Cover what went well, one thing to improve, and one task for next time. Do not repeat any personal details. "
    "Then add one last line exactly in this form: SCORE: <a whole number from 0 to 100>, "
    "judging how well the student did in this lesson for their level."
)


def _transcript(session: TutorSession) -> str:
    lines = [f"{'Student' if m.role == 'user' else 'Teacher'}: {m.content}" for m in session.messages[-40:]]
    return "\n".join(lines)


def evaluate_session(db: DBSession, session: TutorSession) -> None:
    # Written once, when the lesson ends. The same answer gives the score (0 to 100), which the averages use.
    # Lessons with no student turns get no evaluation and no score.
    if session.score is not None or session.status != "completed" or not session.messages:
        return
    student = db.get(Student, session.student_id)
    result = complete(EVALUATION_INSTRUCTIONS, [{"role": "user", "content": _transcript(session)}], max_tokens=400)
    text, score = split_score(result.text)
    if not session.evaluation:
        session.evaluation = text
    session.score = score
    tenant = db.get(Tenant, student.tenant_id)
    record_usage(db, tenant, session.id, result.input_tokens, result.output_tokens)
    db.commit()


def score_pending_sessions(db: DBSession, student_id: str) -> None:
    # Finished lessons that have no score yet are scored before the next lesson starts.
    pending = (
        db.query(TutorSession)
        .filter(TutorSession.student_id == student_id, TutorSession.status == "completed", TutorSession.score.is_(None))
        .all()
    )
    for session in pending:
        evaluate_session(db, session)


def past_evaluations(db: DBSession, student_id: str, limit: int = 3) -> str:
    rows = (
        db.query(TutorSession)
        .filter(TutorSession.student_id == student_id, TutorSession.evaluation.isnot(None))
        .order_by(TutorSession.started_at.desc())
        .limit(limit)
        .all()
    )
    return "\n".join(f"- {r.started_at:%Y-%m-%d}: {r.evaluation}" for r in rows)


def course_note(db: DBSession, student: Student) -> str:
    # Where the learner is in the lesson path, for the evaluation of the lesson.
    upcoming = next_topic(db, student)
    if upcoming is None:
        return ""
    number, total, topic = upcoming
    return f"Next lesson {number} of {total}: {topic.title}.\n"