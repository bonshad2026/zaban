# The conversation partner's part of «خودت رو محک بزن» (docs/conversation-partner.md, sections 4.14, 14.3 and 14.6).
# Every finished test updates the notebook. Speaking and mixed tests also give the five criteria, which take part in the level rule.
# The report and score stay as they are; what is written here is all-or-nothing, like a lesson.
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from zaban.models import Guardian, SelfTest, Student, Tenant, utcnow
from zaban.services.partner_end import MAX_ATTEMPTS, SUMMARY_INSTRUCTIONS, Calls, read_summary, transcript, write_notebook
from zaban.services.partner_levels import apply_criteria, recent_evaluations
from zaban.services.partner_notebook import save_notebook
from zaban.services.partner_settings import partner_value

CRITERIA_SKILLS = ("speaking", "mixed")


def _event(test: SelfTest, criteria: dict | None, changes: dict) -> str:
    lines = [f"Self-test on {test.created_at:%Y-%m-%d}, {test.minutes} minutes, kind {test.kind}, skill {test.skill}."]
    if criteria is not None:
        lines.append("Criteria in this test: " + ", ".join(f"{key} {value}" for key, value in criteria.items()) + ".")
        lines.append("Level changes: " + (", ".join(f"{key} {old} to {new}" for key, (old, new) in changes.items()) or "none") + ".")
    lines.append("Score: " + (f"{test.score:.0f}" if test.score is not None else "none"))
    lines.append(f"Report: {test.result or 'none'}")
    return "\n".join(lines)


def run_test_update(db: DBSession, student: Student, test: SelfTest, now: datetime) -> str:
    # Returns the new partner status. A failed run saves nothing and is tried again later, or stops at no_evaluation.
    if test.partner_status == "evaluated":
        return test.partner_status
    attempts = test.partner_attempts + 1
    try:
        owner = db.get(Guardian, student.self_owner_id) if student.self_owner_id else None
        calls = Calls(db, db.get(Tenant, student.tenant_id), test.id)
        criteria = None
        changes: dict = {}
        if test.skill in CRITERIA_SKILLS:
            criteria = read_summary(calls(SUMMARY_INSTRUCTIONS, transcript(test.messages), 600).text)["criteria"]
            window = max(int(partner_value(db, "partner_level_up_sessions")), int(partner_value(db, "partner_level_down_sessions")))
            history = recent_evaluations(db, student.id, test.id, window)
            changes = apply_criteria(db, student, test, criteria, history)
        max_words = int(partner_value(db, "partner_memory_max_words"))
        notebook = write_notebook(calls, student, db, _event(test, criteria, changes), max_words)
        save_notebook(db, student, notebook, "self_test", now)
        if owner is not None:
            owner.plan_tokens_used += calls.used
        test.partner_attempts = attempts
        test.partner_status = "evaluated"
        db.commit()
    except Exception:
        db.rollback()
        test.partner_attempts = attempts
        test.partner_status = "pending" if attempts < MAX_ATTEMPTS else "no_evaluation"
        db.commit()
    return test.partner_status


def finish_partner_test(db: DBSession, student: Student, test: SelfTest) -> str:
    return run_test_update(db, student, test, utcnow())


def reprocess_test(db: DBSession, student: Student, test: SelfTest) -> str:
    # The administrator asks for another try. Only tests that are waiting or closed without an update can be tried again.
    if test.partner_status in ("pending", "no_evaluation"):
        test.partner_status = "pending"
        test.partner_attempts = 0
        db.commit()
        return run_test_update(db, student, test, utcnow())
    return test.partner_status
