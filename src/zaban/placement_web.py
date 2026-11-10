from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from zaban.db import get_db
from zaban.services.placement_test import (
    SKILLS,
    answer,
    ensure_bank,
    placement_state,
    skill_view,
    skip,
    start_attempt,
    latest_attempt,
)
from zaban.web import _student_from_cookie

# The level test for the learner. Each skill is scored on its own. The answers are checked on the server.
router = APIRouter(prefix="/web/placement")


class AnswerIn(BaseModel):
    question_id: int
    option: int = Field(ge=0, le=10)


def _skill_or_404(skill: str) -> str:
    if skill not in SKILLS:
        raise HTTPException(status_code=404, detail="Not found")
    return skill


@router.get("/state")
def read_state(zaban_student: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> dict:
    student = _student_from_cookie(db, zaban_student)
    ensure_bank(db)
    return placement_state(db, student)


@router.post("/{skill}/start")
def start(skill: str, zaban_student: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> dict:
    student = _student_from_cookie(db, zaban_student)
    _skill_or_404(skill)
    ensure_bank(db)
    start_attempt(db, student, skill)
    return skill_view(db, student, skill)


@router.post("/{skill}/answer")
def give_answer(
    skill: str,
    body: AnswerIn,
    zaban_student: str | None = Cookie(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    student = _student_from_cookie(db, zaban_student)
    _skill_or_404(skill)
    attempt = latest_attempt(db, student, skill)
    if attempt is None or attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="This part of the test is not running")
    try:
        answer(db, student, attempt, body.question_id, body.option)
    except ValueError as err:
        raise HTTPException(status_code=409, detail=str(err))
    return skill_view(db, student, skill)


@router.post("/{skill}/skip")
def skip_skill(skill: str, zaban_student: str | None = Cookie(default=None), db: DBSession = Depends(get_db)) -> dict:
    student = _student_from_cookie(db, zaban_student)
    _skill_or_404(skill)
    attempt = latest_attempt(db, student, skill)
    if attempt is None or attempt.status != "in_progress":
        raise HTTPException(status_code=409, detail="This part of the test is not running")
    skip(db, student, attempt)
    return skill_view(db, student, skill)
