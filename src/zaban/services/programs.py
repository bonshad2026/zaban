from sqlalchemy.orm import Session as DBSession

from zaban.models import LearningProgram, LessonItem, ProgramItem, Student, StudentGoal, StudentProgress, TutorSession
from zaban.program_data import PROGRAM_ITEMS, PROGRAM_TITLES_EN, PROGRAMS
from zaban.services.curriculum import band_code

# A learner who has not chosen a goal gets the everyday conversation program.
DEFAULT_GOAL = "daily_conversation"


def seed_programs(db: DBSession) -> None:
    # Adds programs and items that are missing. A program that already has items is left as the administrator wrote it.
    for data in PROGRAMS:
        if db.get(LearningProgram, data["id"]) is None:
            db.add(LearningProgram(**data))
            db.flush()
        has_items = db.query(ProgramItem).filter(ProgramItem.program_id == data["id"]).first() is not None
        if not has_items:
            for position, (title, activity, phrases) in enumerate(PROGRAM_ITEMS.get(data["id"], [])):
                db.add(ProgramItem(program_id=data["id"], position=position, title=title, activity=activity, phrases=phrases))
    # Lessons without an English title get the one from the program data. Titles the administrator wrote are kept.
    for program_id, titles in PROGRAM_TITLES_EN.items():
        for item in db.query(ProgramItem).filter(ProgramItem.program_id == program_id, ProgramItem.title_en.is_(None)).all():
            if item.position < len(titles):
                item.title_en = titles[item.position]
    db.commit()


def program_for(db: DBSession, student: Student) -> LearningProgram | None:
    band = band_code(student.age_band)
    level = student.cefr_level
    if band is None or level is None:
        return None
    goal_row = db.get(StudentGoal, student.id)
    goal = goal_row.goal if goal_row else DEFAULT_GOAL
    return (
        db.query(LearningProgram)
        .filter(LearningProgram.band == band, LearningProgram.level == level, LearningProgram.goal == goal)
        .first()
    )


def ensure_progress(db: DBSession, student: Student) -> StudentProgress | None:
    # Starts a learner's place in the program that fits them. Returns None when no program fits.
    program = program_for(db, student)
    if program is None:
        return None
    progress = db.get(StudentProgress, student.id)
    if progress is None:
        progress = StudentProgress(student_id=student.id, program_id=program.id, position=0, status="active")
        db.add(progress)
        db.flush()
    return progress


def total_items(db: DBSession, program_id: str) -> int:
    return db.query(ProgramItem).filter(ProgramItem.program_id == program_id).count()


def _last_lesson(db: DBSession, student_id: str) -> LessonItem | None:
    return (
        db.query(LessonItem)
        .join(TutorSession, TutorSession.id == LessonItem.session_id)
        .filter(TutorSession.student_id == student_id)
        .order_by(LessonItem.created_at.desc())
        .first()
    )


def advance_if_done(db: DBSession, student_id: str) -> None:
    # A lesson that has ended moves the learner to the next item, once. A block of lessons then waits for approval.
    progress = db.get(StudentProgress, student_id)
    last = _last_lesson(db, student_id)
    if progress is None or last is None or last.counted:
        return
    session = db.get(TutorSession, last.session_id)
    if session is None or session.status != "completed":
        return
    last.counted = True
    program = db.get(LearningProgram, progress.program_id)
    progress.position += 1
    if progress.position >= total_items(db, program.id):
        progress.status = "finished"
    elif progress.position % program.block_size == 0:
        progress.status = "waiting_approval"


def current_item(db: DBSession, progress: StudentProgress) -> ProgramItem | None:
    return (
        db.query(ProgramItem)
        .filter(ProgramItem.program_id == progress.program_id, ProgramItem.position == progress.position)
        .first()
    )


def record_lesson(db: DBSession, session_id: str, progress: StudentProgress, item: ProgramItem) -> None:
    program = db.get(LearningProgram, progress.program_id)
    db.add(
        LessonItem(
            session_id=session_id,
            program_id=program.id,
            position=item.position,
            program_version=program.version,
        )
    )


def lesson_item_for(db: DBSession, session_id: str) -> tuple[LearningProgram, ProgramItem] | None:
    record = db.get(LessonItem, session_id)
    if record is None:
        return None
    item = (
        db.query(ProgramItem)
        .filter(ProgramItem.program_id == record.program_id, ProgramItem.position == record.position)
        .first()
    )
    return (db.get(LearningProgram, record.program_id), item) if item else None


def approve_block(progress: StudentProgress) -> None:
    if progress.status == "waiting_approval":
        progress.status = "active"


def program_note(program: LearningProgram, item: ProgramItem, total: int) -> str:
    # The part of the lesson prompt that tells the model which program lesson this is.
    phrases = ", ".join(f'"{p}"' for p in item.phrases) or "none"
    return (
        f"Program lesson {item.position + 1} of {total} ({program.name}).\n"
        f"Lesson title: {item.title}. Activity: {item.activity}.\n"
        f"Target phrases to practise: {phrases}. Use them naturally; do not list them all at once."
    )
