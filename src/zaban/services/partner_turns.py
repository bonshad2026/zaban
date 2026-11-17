# Writes what one valid partner answer says about the learner (docs/conversation-partner.md, sections 3.1, 3.2, 3.3 and 13.3).
# Only a valid answer reaches this code. Nothing here runs for a plain-text answer.
from datetime import datetime, timedelta

from sqlalchemy.orm import Session as DBSession

from zaban.models import LearnerError, LearnerPhrase, PhraseItem, PhraseReview, SessionLogEntry, Student
from zaban.services.partner_output import PartnerTurn
from zaban.services.partner_phrases import phrase_settings
from zaban.services.phrase_library import phrase_key


def _padded(text: str) -> str:
    # Spaces at both ends, so a phrase matches only as whole words.
    return f" {phrase_key(text)} "


def _count_error(db: DBSession, student: Student, session_id: str, feedback: dict, now: datetime) -> None:
    row = db.query(LearnerError).filter(LearnerError.student_id == student.id, LearnerError.error_type == feedback["error_type"]).first()
    if row is None:
        row = LearnerError(student_id=student.id, error_type=feedback["error_type"], count=0)
        db.add(row)
    row.count += 1
    row.last_session_id = session_id
    row.last_seen_at = now
    db.add(SessionLogEntry(
        session_id=session_id,
        student_id=student.id,
        kind="error",
        key=feedback["error_type"],
        detail=f"{feedback['original']} -> {feedback['better']}",
        created_at=now,
    ))


def _introduce(db: DBSession, student: Student, session_id: str, new_phrase: dict, now: datetime) -> None:
    key = phrase_key(new_phrase["text"])
    item = db.query(PhraseItem).filter(PhraseItem.text_key == key).first()
    if item is None:
        # Not in the library: it waits in the review queue for the administrator (section 6).
        waiting = db.query(PhraseReview).filter(PhraseReview.text_key == key, PhraseReview.status == "pending").first()
        if waiting is None:
            db.add(PhraseReview(
                text=new_phrase["text"],
                text_key=key,
                situation=new_phrase["situation"],
                register=new_phrase["register"],
                student_id=student.id,
                session_id=session_id,
            ))
        return
    if db.query(LearnerPhrase).filter(LearnerPhrase.student_id == student.id, LearnerPhrase.phrase_id == item.id).first() is None:
        db.add(LearnerPhrase(student_id=student.id, phrase_id=item.id, status="seen", clean_sessions=0, review_step=0))
        db.add(SessionLogEntry(session_id=session_id, student_id=student.id, kind="phrase", key=str(item.id), detail="seen", created_at=now))


def _track_usage(db: DBSession, student: Student, session_id: str, turn: PartnerTurn, user_text: str, now: datetime) -> None:
    # A phrase counts as used when the learner's own message contains it. It counts toward mastery only when the
    # answer had no correction on that phrase, and only once per separate conversation.
    settings = phrase_settings(db)
    intervals = settings["intervals"] or [3]
    said = _padded(user_text)
    help_text = _padded(turn.feedback["original"]) if turn.feedback else ""
    for item in db.query(PhraseItem).all():
        key = _padded(item.text)
        if not key.strip() or key not in said:
            continue
        row = db.query(LearnerPhrase).filter_by(student_id=student.id, phrase_id=item.id).first()
        if row is None:
            # The learner used a library phrase the partner did not introduce in this conversation.
            row = LearnerPhrase(student_id=student.id, phrase_id=item.id, status="used", clean_sessions=0, review_step=0)
            db.add(row)
            db.flush()
        new_session = row.last_session_id != session_id
        clean = key not in help_text
        if row.status == "mastered":
            if clean and new_session:
                row.review_step = min(row.review_step + 1, len(intervals) - 1)
                row.next_review_at = now + timedelta(days=intervals[row.review_step])
        elif clean:
            if new_session:
                row.clean_sessions += 1
            if row.clean_sessions >= settings["mastery"]:
                row.status = "mastered"
                row.review_step = 0
                row.next_review_at = now + timedelta(days=intervals[0])
            else:
                row.status = "used"
        elif row.status == "seen":
            row.status = "used"
        row.last_session_id = session_id
        db.add(SessionLogEntry(session_id=session_id, student_id=student.id, kind="phrase", key=str(row.phrase_id), detail=row.status, created_at=now))


def apply_turn(db: DBSession, student: Student, session_id: str, turn: PartnerTurn, user_text: str, now: datetime) -> None:
    if turn.feedback:
        _count_error(db, student, session_id, turn.feedback, now)
    if turn.new_phrase:
        _introduce(db, student, session_id, turn.new_phrase, now)
    _track_usage(db, student, session_id, turn, user_text, now)
    db.flush()
