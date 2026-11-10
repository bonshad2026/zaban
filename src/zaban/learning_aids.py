from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from zaban.db import get_db
from zaban.models import (
    BillingPlan,
    HelpContent,
    LearnerDetails,
    LearningProgram,
    Payment,
    Plan,
    ProgramItem,
    SelfTest,
    SelfTestMessage,
    Student,
    StudentProgress,
    TutorSession,
)
from zaban.schemas import DetailsUpdate, LevelUpdate, SelfTestAnswer, SelfTestCreate
from zaban.services.learner_details import details_out, save_details
from zaban.services.curriculum import band_code
from zaban.services.help_content import GENDERS, LEVELS, facet_tree, tags_by_content
from zaban.services.self_test import answer_test, finish_test, owned_test, start_test
from zaban.web import _guardian_from_cookie, _student_from_cookie

# Student-facing learning aids: the help content library and the self-test ("خودت رو محک بزن").
router = APIRouter(prefix="/web/student")
# A parent reads and edits the details and progress of their own children.
parent_router = APIRouter(prefix="/web/parent")


def _matches(item: HelpContent, student: Student) -> bool:
    # Same rule as the list: the age band must match, and the level too once the learner has one.
    if item.age_band != band_code(student.age_band):
        return False
    return student.cefr_level is None or item.level == student.cefr_level


def _visible_query(db: DBSession, student: Student, category: str | None):
    # What the learner may see: their age band, their level once they have one, and the chosen category.
    query = db.query(HelpContent).filter(HelpContent.age_band == band_code(student.age_band))
    if student.cefr_level:
        query = query.filter(HelpContent.level == student.cefr_level)
    if category:
        query = query.filter(HelpContent.category == category)
    return query


def _filtered(items: list[HelpContent], tags: dict[str, list], level: str | None, gender: str | None, tag_ids: list[str], needle: str) -> list[HelpContent]:
    # Each chosen filter must match. Content for everyone (no gender) matches every gender filter.
    out = []
    for item in items:
        item_tag_ids = {t.id for t in tags.get(item.id, [])}
        if level and item.level != level:
            continue
        if gender and item.gender not in (None, gender):
            continue
        if any(tag_id not in item_tag_ids for tag_id in tag_ids):
            continue
        if needle and needle not in item.title.lower() and not any(needle in t.label.lower() for t in tags.get(item.id, [])):
            continue
        out.append(item)
    return out


@router.get("/help-content")
def list_help_content(
    category: str | None = None,
    q: str | None = None,
    level: str | None = None,
    gender: str | None = None,
    tag: list[str] = Query(default=[]),
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> list[dict]:
    student = _student_from_cookie(db, zaban_student)
    rows = _visible_query(db, student, category).order_by(HelpContent.created_at.desc()).limit(200).all()
    tags = tags_by_content(db, [item.id for item in rows])
    needle = (q or "").strip().lower()
    out = []
    for item in _filtered(rows, tags, level, gender, tag, needle):
        out.append(
            {
                "id": item.id,
                "title": item.title,
                "category": item.category,
                "level": item.level,
                "tags": [t.label for t in tags.get(item.id, [])],
                "stage": item.stage,
                "url": item.url,
                "mime": item.mime,
                "has_file": item.data is not None,
            }
        )
    return out


@router.get("/help-content/filters")
def help_content_filters(
    category: str | None = None,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    # The choices for the learner's filter dialog. Only values that some visible item has are listed, with the count.
    student = _student_from_cookie(db, zaban_student)
    rows = _visible_query(db, student, category).all()
    tags = tags_by_content(db, [item.id for item in rows])

    def options(pairs: list[tuple[str, str, int]]) -> list[dict]:
        return [{"value": v, "label": label, "count": n} for v, label, n in pairs if n]

    levels = [(lv, lv, sum(1 for i in rows if i.level == lv)) for lv in LEVELS]
    genders = [(g, label, sum(1 for i in rows if i.gender == g)) for g, label in GENDERS.items()]
    counts = {}
    for item_tags in tags.values():
        for t in item_tags:
            counts[t.id] = counts.get(t.id, 0) + 1
    facets = []
    for facet in facet_tree(db):
        pairs = [(t["id"], t["label"], counts.get(t["id"], 0)) for t in facet["tags"]]
        facets.append({"key": f"tag:{facet['id']}", "label": facet["name"], "options": options(pairs)})
    return {
        "level": {"label": "سطح", "options": options(levels)},
        "gender": {"label": "جنسیت", "options": options(genders)},
        "facets": [f for f in facets if f["options"]],
    }


@router.get("/help-content/{item_id}/file")
def help_content_file(
    item_id: str,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> Response:
    student = _student_from_cookie(db, zaban_student)
    item = db.get(HelpContent, item_id)
    if item is None or item.data is None or not _matches(item, student):
        raise HTTPException(status_code=404, detail="Not found")
    # Served inline for viewing or listening; the browser download button adds the attachment header.
    return Response(content=item.data, media_type=item.mime, headers={"Cache-Control": "private, max-age=3600"})


def _test_out(test: SelfTest, db: DBSession) -> dict:
    messages = (
        db.query(SelfTestMessage).filter(SelfTestMessage.test_id == test.id).order_by(SelfTestMessage.id).all()
    )
    return {
        "id": test.id,
        "kind": test.kind,
        "skill": test.skill,
        "minutes": test.minutes,
        "level": test.level_used,
        "status": test.status,
        "ends_at": test.ends_at.isoformat(),
        "score": test.score,
        "result": test.result,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
    }


@router.get("/self-tests")
def list_self_tests(
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> list[dict]:
    # The learner's earlier tests, newest first, with the evaluation written at the end of each.
    student = _student_from_cookie(db, zaban_student)
    rows = (
        db.query(SelfTest)
        .filter(SelfTest.student_id == student.id)
        .order_by(SelfTest.created_at.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "id": t.id,
            "kind": t.kind,
            "skill": t.skill,
            "minutes": t.minutes,
            "level": t.level_used,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
            "score": t.score,
            "result": t.result,
        }
        for t in rows
    ]


@router.post("/self-tests", status_code=201)
def create_self_test(
    body: SelfTestCreate,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    student = _student_from_cookie(db, zaban_student)
    test = start_test(db, student, body.kind, body.skill, body.minutes)
    return _test_out(test, db)


@router.get("/self-tests/{test_id}")
def read_self_test(
    test_id: str,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    student = _student_from_cookie(db, zaban_student)
    return _test_out(owned_test(db, student, test_id), db)


@router.post("/self-tests/{test_id}/messages")
def answer_self_test(
    test_id: str,
    body: SelfTestAnswer,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    student = _student_from_cookie(db, zaban_student)
    test = answer_test(db, student, owned_test(db, student, test_id), body.content)
    return _test_out(test, db)


@router.post("/self-tests/{test_id}/finish")
def end_self_test(
    test_id: str,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    student = _student_from_cookie(db, zaban_student)
    test = finish_test(db, student, owned_test(db, student, test_id))
    return _test_out(test, db)


# ----- Learner details, level, progress and payments -----

def _progress_out(db: DBSession, student: Student) -> dict:
    progress = db.get(StudentProgress, student.id)
    sessions = (
        db.query(TutorSession)
        .filter(TutorSession.student_id == student.id, TutorSession.status == "completed")
        .order_by(TutorSession.started_at.desc())
        .limit(20)
        .all()
    )
    out = {
        "program": None,
        "stages": [],
        "position": 0,
        "total": 0,
        "percent": 0.0,
        "session_number": len(sessions) + 1,
        "pace": {"sessions_per_week": None, "expected_week": None},
        "sessions": [
            {"id": s.id, "started_at": s.started_at.isoformat(), "score": s.score, "evaluation": s.evaluation}
            for s in sessions
        ],
    }
    if progress is None:
        return out
    program = db.get(LearningProgram, progress.program_id)
    items = db.query(ProgramItem).filter(ProgramItem.program_id == program.id).order_by(ProgramItem.position).all()
    stages: dict[str, dict] = {}
    for item in items:
        name = item.stage or "Lessons"
        entry = stages.setdefault(name, {"name": name, "total": 0, "done": 0})
        entry["total"] += 1
        if item.position < progress.position:
            entry["done"] += 1
    for entry in stages.values():
        entry["percent"] = round(100 * entry["done"] / entry["total"], 1) if entry["total"] else 0.0
    total = len(items)
    # Pace is set by the learner's plan (sessions per week). The expected week follows from it.
    plan = db.query(Plan).filter(Plan.student_id == student.id, Plan.status == "active").first()
    per_week = plan.sessions_per_week if plan else None
    expected_week = (progress.position // per_week + 1) if per_week else None
    out.update(
        program={"name": program.name, "duration_months": program.duration_months, "status": progress.status},
        pace={"sessions_per_week": per_week, "expected_week": expected_week},
        stages=list(stages.values()),
        position=progress.position,
        total=total,
        percent=round(100 * progress.position / total, 1) if total else 0.0,
    )
    return out


@router.get("/details")
def read_details(zaban_student: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> dict:
    student = _student_from_cookie(db, zaban_student)
    from zaban.services.placement_test import skill_levels

    return {"details": details_out(db.get(LearnerDetails, student.id)), "skill_levels": skill_levels(student)}


class SkillLevelsUpdate(BaseModel):
    # Each skill is optional. Only the skills that are sent change.
    listening: str | None = Field(default=None, pattern=r"^(A1|A2|B1|B2|C1)$")
    reading: str | None = Field(default=None, pattern=r"^(A1|A2|B1|B2|C1)$")
    grammar: str | None = Field(default=None, pattern=r"^(A1|A2|B1|B2|C1)$")
    speaking_writing: str | None = Field(default=None, pattern=r"^(A1|A2|B1|B2|C1)$")


@router.put("/skill-levels")
def set_skill_levels(
    body: SkillLevelsUpdate,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    from zaban.services.placement_test import skill_levels

    student = _student_from_cookie(db, zaban_student)
    columns = {
        "listening": "level_listening",
        "reading": "level_reading",
        "grammar": "level_grammar",
        "speaking_writing": "level_speaking_writing",
    }
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(student, columns[key], value)
    db.commit()
    return {"skill_levels": skill_levels(student)}


@router.put("/details")
def save_my_details(
    body: DetailsUpdate,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    student = _student_from_cookie(db, zaban_student)
    save_details(db, student.id, body.model_dump(exclude_unset=True))
    db.commit()
    return {"details": details_out(db.get(LearnerDetails, student.id))}


@router.put("/level")
def set_my_level(
    body: LevelUpdate,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    # The learner can enter the level directly, or take the short test. Either way it is saved in the database.
    student = _student_from_cookie(db, zaban_student)
    student.cefr_level = body.cefr_level
    db.commit()
    return {"cefr_level": student.cefr_level}


@router.get("/progress")
def my_progress(zaban_student: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> dict:
    student = _student_from_cookie(db, zaban_student)
    return _progress_out(db, student)


@router.get("/payments")
def my_payments(zaban_student: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> list[dict]:
    student = _student_from_cookie(db, zaban_student)
    owner = student.guardian_id or student.self_owner_id
    if owner is None:
        return []
    rows = db.query(Payment).filter(Payment.guardian_id == owner).order_by(Payment.created_at.desc()).all()
    out = []
    for p in rows:
        plan = db.get(BillingPlan, p.plan_id)
        out.append(
            {
                "id": p.id,
                "plan_name": plan.name if plan else "",
                "plan_name_en": plan.name_en if plan else None,
                "amount_toman": p.amount_toman,
                "status": p.status,
                "created_at": p.created_at.isoformat(),
                "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
            }
        )
    return out


# ----- A parent's view of a child: the same details, progress and evaluations -----

def _child_for_guardian(db: DBSession, zaban_parent: str | None, student_id: str) -> Student:
    guardian = _guardian_from_cookie(db, zaban_parent)
    student = db.get(Student, student_id)
    if student is None or student.guardian_id != guardian.id:
        raise HTTPException(status_code=404, detail="Not found")
    return student


@parent_router.get("/children/{student_id}/details")
def child_details(student_id: str, zaban_parent: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> dict:
    child = _child_for_guardian(db, zaban_parent, student_id)
    return {"details": details_out(db.get(LearnerDetails, child.id)), "cefr_level": child.cefr_level}


@parent_router.put("/children/{student_id}/details")
def save_child_details(
    student_id: str,
    body: DetailsUpdate,
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    child = _child_for_guardian(db, zaban_parent, student_id)
    save_details(db, child.id, body.model_dump(exclude_unset=True))
    db.commit()
    return {"details": details_out(db.get(LearnerDetails, child.id))}


@parent_router.get("/children/{student_id}/progress")
def child_progress(student_id: str, zaban_parent: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> dict:
    return _progress_out(db, _child_for_guardian(db, zaban_parent, student_id))
