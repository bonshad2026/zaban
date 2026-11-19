# The end-of-lesson routine of the conversation partner (docs/conversation-partner.md, sections 6.2, 13.7, 14.4 and 15.5).
# The summary, the criteria, the level changes and the notebook are saved together, or none of them is saved.
# The judging and notebook steps are shared with the self-test (services/partner_selftest.py).
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from zaban.models import Guardian, Message, PhraseItem, SessionLogEntry, Student, Tenant, TutorSession, utcnow
from zaban.services.ai_gateway import AIResult, complete
from zaban.services.metering import record_usage
from zaban.services.evaluations import record_evaluation
from zaban.services.learner_analysis import update_analysis
from zaban.services.partner_levels import CRITERION_COLUMNS, apply_criteria, recent_evaluations
from zaban.services.partner_notebook import NOTEBOOK_RULES, current_notebook, notebook_problems, save_notebook
from zaban.services.partner_output import read_json_object
from zaban.services.partner_policy import LEVEL_CODES
from zaban.services.partner_settings import partner_value

# After this many failed tries the lesson is kept without an evaluation (section 13.7).
MAX_ATTEMPTS = 3
SUMMARY_INSTRUCTIONS = (
    "You judge one English lesson for a learner. Reply with one JSON object and nothing else:\n"
    '{"criteria": {"range": "<CEFR level A1 to C2>", "accuracy": "...", "fluency": "...", "interaction": "...", "coherence": "..."}, '
    '"summary": "<3 to 5 sentences in English about this lesson>"}\n'
    "Judge each criterion for this lesson only: range (vocabulary), accuracy (grammar and errors), fluency (speed and flow), "
    "interaction (taking turns, asking and answering), coherence (linking sentences). Do not write personal details."
)


class EndError(Exception):
    # A part of the routine could not be written. Nothing from this run is saved.
    pass


def transcript(messages: list[Message]) -> str:
    return "\n".join(f"{'Student' if m.role == 'user' else 'Teacher'}: {m.content}" for m in messages[-40:])


def read_summary(text: str) -> dict:
    data = read_json_object(text)
    if not data or not isinstance(data.get("criteria"), dict) or not isinstance(data.get("summary"), str):
        raise EndError("summary is not in the contract")
    criteria = data["criteria"]
    if any(criteria.get(key) not in LEVEL_CODES for key in CRITERION_COLUMNS):
        raise EndError("summary has a criterion outside A1 to C2")
    if not data["summary"].strip():
        raise EndError("summary is empty")
    return {"criteria": {key: criteria[key] for key in CRITERION_COLUMNS}, "summary": data["summary"].strip()[:1500]}


class Calls:
    # Counts the tokens of every model call of one run, and records each one against the tenant.
    def __init__(self, db: DBSession, tenant: Tenant, record_id: str):
        self.db, self.tenant, self.record_id, self.used = db, tenant, record_id, 0

    def __call__(self, system: str, user: str, max_tokens: int) -> AIResult:
        result = complete(system, [{"role": "user", "content": user}], max_tokens=max_tokens)
        record_usage(self.db, self.tenant, self.record_id, result.input_tokens, result.output_tokens)
        self.used += result.input_tokens + result.output_tokens
        return result


def write_notebook(calls: Calls, student: Student, db: DBSession, event: str, max_words: int) -> str:
    # Asks for the whole notebook again, with the event. Two tries; a notebook that fails the checks is never saved.
    user = f"Current notebook:\n{current_notebook(db, student) or '(empty: this is the first update)'}\n\nNew event:\n{event}"
    # The administrator can change the writing rule; the code's rule is used when that setting is empty.
    rules = (partner_value(db, "partner_notebook_rules") or NOTEBOOK_RULES).replace("{max_words}", str(max_words))
    for _ in range(2):
        text = calls(rules, user, 3000).text.strip()
        if not notebook_problems(text, max_words, student.display_name or ""):
            return text
    raise EndError("notebook was refused twice")


def _event_text(db: DBSession, session: TutorSession, learner_turns: int, summary: dict, changes: dict) -> str:
    # What happened in the lesson, in plain words. The notebook writer reads this, not the raw numbers stored elsewhere.
    logs = db.query(SessionLogEntry).filter(SessionLogEntry.session_id == session.id).order_by(SessionLogEntry.id).all()
    errors: dict[str, int] = {}
    phrases = []
    for log in logs:
        if log.kind == "error":
            errors[log.key] = errors.get(log.key, 0) + 1
        elif log.kind == "phrase":
            item = db.get(PhraseItem, int(log.key))
            if item is not None:
                phrases.append(f"{item.text} ({log.detail})")
    levels = ", ".join(f"{key} {value}" for key, value in summary["criteria"].items())
    moved = ", ".join(f"{key} {old} to {new}" for key, (old, new) in changes.items()) or "none"
    return "\n".join(
        [
            f"Lesson on {session.started_at:%Y-%m-%d}, {session.duration_minutes} minutes, {learner_turns} learner messages.",
            f"Criteria in this lesson: {levels}.",
            f"Level changes: {moved}.",
            "Errors in this lesson: " + (", ".join(f"{k} x{v}" for k, v in errors.items()) or "none"),
            "Phrases in this lesson: " + ("; ".join(phrases) or "none"),
            f"Lesson summary: {summary['summary']}",
        ]
    )


def _run(db: DBSession, student: Student, session: TutorSession, messages: list[Message], now: datetime) -> None:
    owner = db.get(Guardian, student.self_owner_id) if student.self_owner_id else None
    calls = Calls(db, db.get(Tenant, student.tenant_id), session.id)
    summary = read_summary(calls(SUMMARY_INSTRUCTIONS, transcript(messages), 600).text)
    window = max(int(partner_value(db, "partner_level_up_sessions")), int(partner_value(db, "partner_level_down_sessions")))
    history = recent_evaluations(db, student.id, session.id, window)
    changes = apply_criteria(db, student, session, summary["criteria"], history)
    session.evaluation = summary["summary"]
    # Every lesson and free talk is kept in the one evaluation table. Its skill is speaking, measured by the five criteria.
    record_evaluation(db, student.id, "free" if session.session_kind == "free" else "lesson", session.id, "speaking",
                      summary["summary"], None, changes)
    max_words = int(partner_value(db, "partner_memory_max_words"))
    learner_turns = sum(1 for m in messages if m.role == "user")
    notebook = write_notebook(calls, student, db, _event_text(db, session, learner_turns, summary, changes), max_words)
    save_notebook(db, student, notebook, "session_end", now)
    if owner is not None:
        owner.plan_tokens_used += calls.used
    update_analysis(db, student, "free" if session.session_kind == "free" else "lesson", now)
    session.end_status = "evaluated"


def finish_partner_session(db: DBSession, session: TutorSession, now: datetime | None = None) -> str:
    # Runs the routine once for a finished lesson of the new engine. Safe to call again: a finished lesson is skipped.
    now = now or utcnow()
    if session.engine != "new" or session.status != "completed" or session.end_status in ("evaluated", "no_evaluation"):
        return session.end_status
    student = db.get(Student, session.student_id)
    messages = db.query(Message).filter(Message.session_id == session.id).order_by(Message.id).all()
    learner_turns = sum(1 for m in messages if m.role == "user")
    if learner_turns < int(partner_value(db, "partner_min_messages_eval")):
        session.end_status = "no_evaluation"
        db.commit()
        return session.end_status
    attempts = session.end_attempts + 1
    try:
        _run(db, student, session, messages, now)
        session.end_attempts = attempts
        db.commit()
    except Exception:
        # Nothing from the failed run is kept. The lesson waits to be processed again, or is closed without an evaluation.
        db.rollback()
        session.end_attempts = attempts
        session.end_status = "pending" if attempts < MAX_ATTEMPTS else "no_evaluation"
        db.commit()
    return session.end_status


def retry_pending(db: DBSession, student_id: str) -> None:
    # Lessons that ended by time without the learner's end (end_status active) are finished here too.
    pending = db.query(TutorSession).filter(
        TutorSession.student_id == student_id,
        TutorSession.engine == "new",
        TutorSession.status == "completed",
        TutorSession.end_status.in_(["pending", "active"]),
    ).all()
    for session in pending:
        finish_partner_session(db, session)


def reprocess(db: DBSession, session: TutorSession) -> str:
    # The administrator asks for another try. Only lessons that are waiting or closed without an evaluation can be tried again.
    if session.end_status in ("pending", "no_evaluation"):
        session.end_status = "pending"
        session.end_attempts = 0
        db.commit()
        finish_partner_session(db, session)
    return session.end_status
