from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from zaban.db import get_db
from zaban.learning_aids import _progress_out
from zaban.models import Guardian, Student
from zaban.reports import _session_rows, _snapshot
from zaban.web import _guardian_from_cookie, _self_profile

# An adult can choose one teacher, using the teacher's referral code. The same code is the teacher's own code.
# A teacher sees the learning report and progress of the adults who chose them, and nobody else.
router = APIRouter(prefix="/web/user")

INVALID_TEACHER_CODE = "This teacher code is not valid"
OWN_CODE = "You cannot choose yourself as your teacher"
NEEDS_CONFIRM = "Please confirm that this is your teacher"


class TeacherCode(BaseModel):
    code: str = Field(min_length=1, max_length=12)


class TeacherChoice(TeacherCode):
    # The learner ticks the box that says this is their teacher. The server refuses the choice without it.
    confirm: bool = False


def _find_teacher(db: DBSession, adult: Guardian, raw_code: str) -> Guardian:
    code = raw_code.strip().upper()
    if code and code == (adult.referral_code or ""):
        raise HTTPException(status_code=400, detail=OWN_CODE)
    teacher = db.query(Guardian).filter(Guardian.referral_code == code).first() if code else None
    if teacher is None:
        raise HTTPException(status_code=400, detail=INVALID_TEACHER_CODE)
    return teacher


def _teacher_out(teacher: Guardian | None) -> dict | None:
    return None if teacher is None else {"id": teacher.id, "name": teacher.full_name}


def _student_for_teacher(db: DBSession, teacher: Guardian, guardian_id: str) -> Guardian:
    # The adult must have chosen this teacher. Anyone else gets the same answer as a missing account.
    student = db.get(Guardian, guardian_id)
    if student is None or student.teacher_id != teacher.id:
        raise HTTPException(status_code=404, detail="Not found")
    return student


@router.get("/teacher")
def read_teacher(
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    adult = _guardian_from_cookie(db, zaban_parent)
    teacher = db.get(Guardian, adult.teacher_id) if adult.teacher_id else None
    return {"teacher": _teacher_out(teacher)}


@router.post("/teacher/lookup")
def lookup_teacher(
    body: TeacherCode,
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    # Shows the name of the adult who owns the code, so the learner can check it before choosing.
    adult = _guardian_from_cookie(db, zaban_parent)
    teacher = _find_teacher(db, adult, body.code)
    return {"teacher": _teacher_out(teacher)}


@router.put("/teacher")
def choose_teacher(
    body: TeacherChoice,
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    adult = _guardian_from_cookie(db, zaban_parent)
    teacher = _find_teacher(db, adult, body.code)
    if not body.confirm:
        raise HTTPException(status_code=400, detail=NEEDS_CONFIRM)
    adult.teacher_id = teacher.id
    db.commit()
    return {"teacher": _teacher_out(teacher)}


@router.delete("/teacher")
def remove_teacher(
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    # The teacher loses access to this adult's report and progress at once.
    adult = _guardian_from_cookie(db, zaban_parent)
    adult.teacher_id = None
    db.commit()
    return {"teacher": None}


@router.get("/students")
def my_students(
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> list[dict]:
    teacher = _guardian_from_cookie(db, zaban_parent)
    students = db.query(Guardian).filter(Guardian.teacher_id == teacher.id).order_by(Guardian.full_name).all()
    out = []
    for student in students:
        profile = _self_profile(db, student)
        out.append({"id": student.id, "name": student.full_name, "level": profile.cefr_level if profile else None})
    return out


@router.get("/students/{guardian_id}/progress")
def student_progress(
    guardian_id: str,
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    teacher = _guardian_from_cookie(db, zaban_parent)
    student = _student_for_teacher(db, teacher, guardian_id)
    profile = _self_profile(db, student)
    if profile is None:
        return {"name": student.full_name, "started": False}
    return {"name": student.full_name, "started": True, **_progress_out(db, profile)}


@router.get("/students/{guardian_id}/report")
def student_report(
    guardian_id: str,
    zaban_parent: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    teacher = _guardian_from_cookie(db, zaban_parent)
    student = _student_for_teacher(db, teacher, guardian_id)
    profile = _self_profile(db, student)
    if profile is None:
        return {"name": student.full_name, "started": False}
    plan, snapshot = _snapshot(db, profile)
    db.commit()
    return {
        "name": student.full_name,
        "started": True,
        "student_id": profile.id,
        "cefr_level": profile.cefr_level,
        "plan": None if plan is None else {"goal": plan.goal, "end_date": plan.end_date.isoformat()},
        **snapshot,
        "sessions": _session_rows(db, profile),
    }
