# Choosing phrases for the partner and reading the phrase settings (docs/conversation-partner.md, sections 3.1, 3.3 and 8.1).
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from zaban.models import LearnerPhrase, PhraseItem, Student
from zaban.services.partner_policy import LEVEL_CODES
from zaban.services.partner_settings import partner_value


def phrase_settings(db: DBSession) -> dict:
    intervals = [int(part) for part in partner_value(db, "partner_review_intervals").split(",") if part.strip()]
    return {
        "per_prompt": int(partner_value(db, "partner_phrases_per_prompt")),
        "errors_per_prompt": int(partner_value(db, "partner_errors_per_prompt")),
        "error_window": int(partner_value(db, "partner_error_window_sessions")),
        "mastery": int(partner_value(db, "partner_mastery_count")),
        "intervals": intervals,
    }


def due_phrases(db: DBSession, student: Student, now: datetime, limit: int) -> list[PhraseItem]:
    # Phrases still being learned come first (seen before used), then mastered phrases that are due for review.
    rows = db.query(LearnerPhrase).filter(LearnerPhrase.student_id == student.id).all()
    waiting = [row for row in rows if row.status in ("seen", "used")]
    due = [row for row in rows if row.status == "mastered" and row.next_review_at is not None and row.next_review_at <= now]
    ordered = sorted(waiting, key=lambda row: (row.status != "seen", row.id)) + sorted(due, key=lambda row: row.next_review_at)
    items = []
    for row in ordered[:limit]:
        item = db.get(PhraseItem, row.phrase_id)
        if item is not None:
            items.append(item)
    return items


def library_candidates(db: DBSession, student: Student, limit: int) -> list[PhraseItem]:
    # New phrases from the library, at the learner's range level or below, that the learner does not have yet.
    if limit <= 0:
        return []
    known = {row.phrase_id for row in db.query(LearnerPhrase.phrase_id).filter(LearnerPhrase.student_id == student.id)}
    allowed = LEVEL_CODES[: LEVEL_CODES.index(student.level_range or "A1") + 1]
    query = db.query(PhraseItem).filter(PhraseItem.level.in_(allowed)).order_by(PhraseItem.id)
    return [item for item in query.limit(limit + len(known)).all() if item.id not in known][:limit]
