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


def ordered_items(db: DBSession, program_id: str) -> list[ProgramItem]:
    return db.query(ProgramItem).filter(ProgramItem.program_id == program_id).order_by(ProgramItem.position).all()


def _completed_lessons(db: DBSession, student_id: str, program_id: str) -> list[tuple[LessonItem, float | None]]:
    rows = (
        db.query(LessonItem, TutorSession.score)
        .join(TutorSession, TutorSession.id == LessonItem.session_id)
        .filter(TutorSession.student_id == student_id, TutorSession.status == "completed", LessonItem.program_id == program_id)
        .order_by(LessonItem.created_at)
        .all()
    )
    return [(lesson, score) for lesson, score in rows]


def _item_id_of(lesson: LessonItem, by_position: dict[int, int]) -> int | None:
    # Lessons written before item ids existed are matched by their position at that time.
    return lesson.item_id if lesson.item_id is not None else by_position.get(lesson.position)


def done_item_ids(db: DBSession, student_id: str, program_id: str) -> set[int]:
    by_position = {item.position: item.id for item in ordered_items(db, program_id)}
    done = set()
    for lesson, _score in _completed_lessons(db, student_id, program_id):
        item_id = _item_id_of(lesson, by_position)
        if item_id is not None:
            done.add(item_id)
    return done


def first_undone_position(db: DBSession, student_id: str, program_id: str) -> int | None:
    # The next lesson is the first item, in the current order, that no completed lesson has covered yet.
    done = done_item_ids(db, student_id, program_id)
    for item in ordered_items(db, program_id):
        if item.id not in done:
            return item.position
    return None


def item_stats(db: DBSession, student_id: str, program_id: str) -> list[dict]:
    # For each item: how many completed lessons covered it, and the average of their scores (None when nothing is scored yet).
    by_position = {item.position: item.id for item in ordered_items(db, program_id)}
    visits: dict[int, int] = {}
    scores: dict[int, list[float]] = {}
    for lesson, score in _completed_lessons(db, student_id, program_id):
        item_id = _item_id_of(lesson, by_position)
        if item_id is None:
            continue
        visits[item_id] = visits.get(item_id, 0) + 1
        if score is not None:
            scores.setdefault(item_id, []).append(score)
    out = []
    for item in ordered_items(db, program_id):
        values = scores.get(item.id, [])
        out.append(
            {
                "item_id": item.id,
                "position": item.position,
                "title": item.title,
                "title_en": item.title_en,
                "visits": visits.get(item.id, 0),
                "average": round(sum(values) / len(values), 1) if values else None,
                "done": visits.get(item.id, 0) > 0,
            }
        )
    return out


def _last_lesson(db: DBSession, student_id: str) -> LessonItem | None:
    return (
        db.query(LessonItem)
        .join(TutorSession, TutorSession.id == LessonItem.session_id)
        .filter(TutorSession.student_id == student_id)
        .order_by(LessonItem.created_at.desc())
        .first()
    )


def advance_if_done(db: DBSession, student_id: str) -> None:
    # A finished lesson is counted once. A normal lesson moves the learner to the first item not yet covered.
    # A lesson the administrator asked to repeat clears that request and leaves the place in the program as it was.
    progress = db.get(StudentProgress, student_id)
    last = _last_lesson(db, student_id)
    if progress is None or last is None or last.counted:
        return
    session = db.get(TutorSession, last.session_id)
    if session is None or session.status != "completed":
        return
    last.counted = True
    by_position = {item.position: item.id for item in ordered_items(db, progress.program_id)}
    if progress.revisit_item_id is not None and _item_id_of(last, by_position) == progress.revisit_item_id:
        progress.revisit_item_id = None
    next_position = first_undone_position(db, student_id, progress.program_id)
    if next_position is None:
        progress.position = total_items(db, progress.program_id)
        progress.status = "finished"
    else:
        progress.position = next_position
        progress.status = "active"


def current_item(db: DBSession, progress: StudentProgress) -> ProgramItem | None:
    # The item for the next lesson: the one asked to be repeated, otherwise the place in the program.
    if progress.revisit_item_id is not None:
        item = db.get(ProgramItem, progress.revisit_item_id)
        if item is not None and item.program_id == progress.program_id:
            return item
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
            item_id=item.id,
            program_version=program.version,
        )
    )


def lesson_item_for(db: DBSession, session_id: str) -> tuple[LearningProgram, ProgramItem] | None:
    record = db.get(LessonItem, session_id)
    if record is None:
        return None
    if record.item_id is not None:
        item = db.get(ProgramItem, record.item_id)
    else:
        item = (
            db.query(ProgramItem)
            .filter(ProgramItem.program_id == record.program_id, ProgramItem.position == record.position)
            .first()
        )
    return (db.get(LearningProgram, record.program_id), item) if item else None


def reorder_items(db: DBSession, program_id: str, item_ids: list[int]) -> None:
    # Writes the new order. Before that, the existing lessons are tied to their items, so their history keeps its meaning.
    items = ordered_items(db, program_id)
    if sorted(item_ids) != sorted(item.id for item in items):
        raise ValueError("The order must list every lesson of the program once")
    by_position = {item.position: item.id for item in items}
    for lesson in db.query(LessonItem).filter(LessonItem.program_id == program_id, LessonItem.item_id.is_(None)).all():
        lesson.item_id = by_position.get(lesson.position)
    by_id = {item.id: item for item in items}
    # The positions are unique per program, so the items first move aside, then take their new places.
    for item in items:
        item.position = -(item.id)
    db.flush()
    for index, item_id in enumerate(item_ids):
        by_id[item_id].position = index
    db.flush()
    for progress in db.query(StudentProgress).filter(StudentProgress.program_id == program_id).all():
        next_position = first_undone_position(db, progress.student_id, program_id)
        if next_position is None:
            progress.position = len(items)
            progress.status = "finished"
        else:
            progress.position = next_position
            if progress.status == "finished":
                progress.status = "active"
    program = db.get(LearningProgram, program_id)
    program.version += 1


def program_note(program: LearningProgram, item: ProgramItem, total: int) -> str:
    # The part of the lesson prompt that tells the model which program lesson this is.
    phrases = ", ".join(f'"{p}"' for p in item.phrases) or "none"
    return (
        f"Program lesson {item.position + 1} of {total} ({program.name}).\n"
        f"Lesson title: {item.title}. Activity: {item.activity}.\n"
        f"Target phrases to practise: {phrases}. Use them naturally; do not list them all at once."
    )
