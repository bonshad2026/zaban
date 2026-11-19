import logging
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from zaban.models import Guardian, LearnerAnalysis, SelfTest, Student, Tenant, TutorSession, utcnow
from zaban.services.ai_gateway import complete
from zaban.services.metering import record_usage
from zaban.services.skill_levels import levels_out

log = logging.getLogger(__name__)

# The analysis is written once after each lesson, free talk or self-test, and the learner sees the latest version.
# Every version is kept, so the history can be shown later.
ANALYSIS_INSTRUCTIONS = (
    "You write the status analysis of one adult learner of English, for the learner. Write in Persian (Farsi), "
    "with exactly these headings, each followed by bullet points:\n"
    "وضعیت کلی:\n"
    "نقاط قوت:\n"
    "نقاط ضعف:\n"
    "پیشرفت نسبت به تحلیل قبلی:\n"
    "گام بعدی:\n"
    "Use only the data given. Name the skills and criteria by their level. If there is no earlier analysis, write one bullet "
    "saying this is the first analysis under the last heading. Keep it under 250 words. Do not write names or personal details."
)
MAX_HISTORY = 10
# The first version for a learner who has no lesson, talk or test yet. It needs no model call.
INITIAL_TEXT = "گزارش اولیه:\n- هنوز جلسه، گفتگو یا آزمونی ثبت نشده است.\n- بعد از اولین فعالیت، تحلیل کامل ساخته می‌شود."
MAX_TEXT = 400


def latest_analysis(db: DBSession, student_id: str) -> LearnerAnalysis | None:
    return (
        db.query(LearnerAnalysis)
        .filter(LearnerAnalysis.student_id == student_id)
        .order_by(LearnerAnalysis.id.desc())
        .first()
    )


def _history_text(db: DBSession, student: Student) -> str:
    # What the model reads: the levels, the latest lessons, free talks and tests with their evaluations, and the earlier analysis.
    levels = levels_out(student)
    skills = ", ".join(f"{key} {levels[key]}" for key in ("listening", "reading", "grammar", "writing", "speaking"))
    criteria = ", ".join(f"{key} {value}" for key, value in levels["criteria"].items())
    sessions = (
        db.query(TutorSession)
        .filter(TutorSession.student_id == student.id, TutorSession.evaluation.isnot(None))
        .order_by(TutorSession.started_at.desc())
        .limit(MAX_HISTORY)
        .all()
    )
    tests = (
        db.query(SelfTest)
        .filter(SelfTest.student_id == student.id, SelfTest.result.isnot(None))
        .order_by(SelfTest.created_at.desc())
        .limit(MAX_HISTORY)
        .all()
    )
    session_lines = [
        f"{s.started_at:%Y-%m-%d} {'free talk' if s.session_kind == 'free' else 'lesson'}: {s.evaluation[:MAX_TEXT]}"
        for s in sessions
    ]
    test_lines = [
        f"{t.created_at:%Y-%m-%d} test {t.skill} score {t.score}: {t.result[:MAX_TEXT]}"
        for t in tests
    ]
    previous = latest_analysis(db, student.id)
    return "\n".join(
        [
            f"Levels: {skills}",
            f"Speaking criteria: {criteria}",
            "Recent lessons and free talks:",
            *(session_lines or ["(none)"]),
            "Recent tests:",
            *(test_lines or ["(none)"]),
            "Earlier analysis:",
            previous.text if previous else "(none)",
        ]
    )


def update_analysis(db: DBSession, student: Student, event: str, now: datetime | None = None) -> None:
    # Writes one new version. The caller commits. A failed or offline reply saves nothing, and the earlier version stays.
    try:
        result = complete(ANALYSIS_INSTRUCTIONS, [{"role": "user", "content": _history_text(db, student)}], max_tokens=700)
    except Exception:
        log.exception("learner analysis could not be written")
        return
    if result.mode != "live" or not result.text.strip():
        return
    record_usage(db, db.get(Tenant, student.tenant_id), student.id, result.input_tokens, result.output_tokens)
    owner = db.get(Guardian, student.self_owner_id) if student.self_owner_id else None
    if owner is not None:
        owner.plan_tokens_used += result.input_tokens + result.output_tokens
    db.add(LearnerAnalysis(student_id=student.id, text=result.text.strip(), event=event, created_at=now or utcnow()))


def _has_history(db: DBSession, student_id: str) -> bool:
    # A lesson, free talk or test that has an evaluation or a result.
    lesson = (
        db.query(TutorSession.id)
        .filter(TutorSession.student_id == student_id, TutorSession.evaluation.isnot(None))
        .first()
    )
    test = db.query(SelfTest.id).filter(SelfTest.student_id == student_id, SelfTest.result.isnot(None)).first()
    return lesson is not None or test is not None


def ensure_analysis(db: DBSession, student: Student) -> LearnerAnalysis | None:
    # The learner's latest analysis. When there is none yet, it is made now from the data the learner already has:
    # a starter report if there is no history, otherwise a full analysis. Later lessons and tests update it.
    row = latest_analysis(db, student.id)
    if row is not None:
        return row
    if _has_history(db, student.id):
        update_analysis(db, student, "backfill")
    else:
        db.add(LearnerAnalysis(student_id=student.id, text=INITIAL_TEXT, event="initial", created_at=utcnow()))
    db.commit()
    return latest_analysis(db, student.id)
