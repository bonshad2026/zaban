from sqlalchemy.orm import Session as DBSession

from zaban.models import Student, StudentProgress, Tenant, TutorSession, ProgramItem, LearningProgram
from zaban.services.ai_gateway import complete
from zaban.services.metering import record_usage

EVALUATION_INSTRUCTIONS = (
    "Write a short evaluation of this English lesson for the parent, in English, in at most five sentences. "
    "Cover what went well, one thing to improve, and one task for next time. Do not repeat any personal details."
)


def _transcript(session: TutorSession) -> str:
    lines = [f"{'Student' if m.role == 'user' else 'Niko'}: {m.content}" for m in session.messages[-40:]]
    return "\n".join(lines)


def evaluate_session(db: DBSession, session: TutorSession) -> None:
    # Written once, when the lesson ends. Lessons with no student turns get no evaluation.
    if session.evaluation or session.status != "completed" or not session.messages:
        return
    student = db.get(Student, session.student_id)
    result = complete(EVALUATION_INSTRUCTIONS, [{"role": "user", "content": _transcript(session)}], max_tokens=300)
    session.evaluation = result.text
    tenant = db.get(Tenant, student.tenant_id)
    record_usage(db, tenant, session.id, result.input_tokens, result.output_tokens)
    db.commit()


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
    progress = db.get(StudentProgress, student.id)
    if progress is None:
        return ""
    program = db.get(LearningProgram, progress.program_id)
    total = db.query(ProgramItem).filter(ProgramItem.program_id == program.id).count()
    item = db.query(ProgramItem).filter(ProgramItem.program_id == program.id, ProgramItem.position == progress.position).first()
    stage = f", stage: {item.stage}" if item and item.stage else ""
    return (
        f"Course: {program.name} ({program.duration_months} months). "
        f"Next lesson {progress.position + 1} of {total}{stage}.\n"
    )
