import re
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession
from starlette.background import BackgroundTask

from zaban.admin import require_admin
from zaban.config import settings
from zaban.db import get_db
from zaban.learning_aids import _progress_out
from zaban.models import (
    ConsultRequest,
    CooperationRequest,
    Guardian,
    LearnerDetails,
    LearningProgram,
    Payment,
    SelfTest,
    Student,
    Tenant,
    TutorSession,
    Usage,
)
from zaban.services.evaluation import past_evaluations
from zaban.services.export import build
from zaban.services.learner_details import details_out
from zaban.services.settings_store import (
    EXPECTED_OUTPUT_KEY,
    PAYMENT_PROVIDER_KEY,
    PROMPT_MODE_DEFAULT,
    PROMPT_MODE_KEY,
    MODE_LABELS,
    get_setting,
    set_setting,
)
from zaban.services.payments import has_active_plan

# Everything the operator panel needs that is not part of the lesson itself.
router = APIRouter(prefix="/admin/api", dependencies=[Depends(require_admin)])

GIT_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/~^-]{0,79}$")


@router.get("/overview")
def overview(db: DBSession = Depends(get_db)) -> dict:
    def count_by(column) -> dict:
        return {value: n for value, n in db.query(column, func.count()).group_by(column).all()}

    tenants = db.query(Tenant).all()
    return {
        "users": {"adults": db.query(Guardian).count(), "learners": db.query(Student).count()},
        "active_plans": sum(1 for g in db.query(Guardian).all() if has_active_plan(g)),
        "payments": count_by(Payment.status),
        "consults": count_by(ConsultRequest.status),
        "cooperations": count_by(CooperationRequest.status),
        "lessons": {"total": db.query(TutorSession).count(), "completed": db.query(TutorSession).filter(TutorSession.status == "completed").count()},
        "self_tests": db.query(SelfTest).count(),
        "tokens": [
            {
                "tenant": t.name,
                "quota": t.quota_tokens,
                "used": t.used_tokens,
                "remaining": max(0, t.quota_tokens - t.used_tokens),
                "percent_used": round(100 * t.used_tokens / t.quota_tokens, 1) if t.quota_tokens else 0.0,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
            }
            for t in tenants
        ],
        "usage_rows": db.query(Usage).count(),
    }


@router.get("/settings")
def read_settings(db: DBSession = Depends(get_db)) -> dict:
    # Secret values are never returned. The panel only shows whether each one is set in the environment.
    return {
        "prompt_mode": get_setting(db, PROMPT_MODE_KEY, PROMPT_MODE_DEFAULT),
        "prompt_mode_labels": MODE_LABELS,
        "expected_output": get_setting(db, EXPECTED_OUTPUT_KEY),
        "payment_provider": get_setting(db, PAYMENT_PROVIDER_KEY, settings.payment_gateway),
        "secrets": {
            "kavenegar_api_key_set": bool(settings.kavenegar_api_key),
            "zarinpal_merchant_id_set": bool(settings.zarinpal_merchant_id),
            "anthropic_api_key_set": bool(settings.anthropic_api_key),
            "sms_otp_template": settings.kavenegar_otp_template,
        },
    }


class SettingsUpdate(BaseModel):
    prompt_mode: str | None = Field(default=None, pattern=r"^(student|general|student_db|all)$")
    expected_output: str | None = Field(default=None, max_length=2000)
    payment_provider: str | None = Field(default=None, pattern=r"^(fake|zarinpal)$")


@router.post("/settings")
def save_settings(body: SettingsUpdate, db: DBSession = Depends(get_db)) -> dict:
    if body.prompt_mode is not None:
        set_setting(db, PROMPT_MODE_KEY, body.prompt_mode)
    if body.expected_output is not None:
        set_setting(db, EXPECTED_OUTPUT_KEY, body.expected_output.strip())
    if body.payment_provider is not None:
        set_setting(db, PAYMENT_PROVIDER_KEY, body.payment_provider)
    db.commit()
    return {"ok": True}


@router.get("/learners/{student_id}")
def learner_detail(student_id: str, db: DBSession = Depends(get_db)) -> dict:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Not found")
    tests = db.query(SelfTest).filter(SelfTest.student_id == student.id).order_by(SelfTest.created_at.desc()).limit(20).all()
    return {
        "id": student.id,
        "display_name": student.display_name,
        "username": student.username,
        "age_band": student.age_band,
        "cefr_level": student.cefr_level,
        "details": details_out(db.get(LearnerDetails, student.id)),
        "progress": _progress_out(db, student),
        "evaluations": past_evaluations(db, student.id, limit=10),
        "self_tests": [{"id": t.id, "kind": t.kind, "skill": t.skill, "status": t.status, "result": t.result} for t in tests],
    }


@router.post("/build")
def download_build(since: str | None = None) -> FileResponse:
    # The build is a zip with the code, the database rows, the media files, and the schema changes.
    if since is not None and not GIT_REF.match(since):
        raise HTTPException(status_code=422, detail="Enter a git branch, tag or commit")
    work = Path(tempfile.mkdtemp(prefix="zaban-build-"))
    try:
        out = work / "zaban-build"
        build(out, since=since, with_data=True, target_url=settings.database_url)
        archive = shutil.make_archive(str(work / "zaban-build"), "zip", out)
    except ValueError as exc:
        shutil.rmtree(work, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(exc))
    return FileResponse(
        archive,
        media_type="application/zip",
        filename="zaban-build.zip",
        background=BackgroundTask(shutil.rmtree, work, True),
    )


class ProgramDuration(BaseModel):
    duration_months: int = Field(ge=1, le=60)


@router.post("/programs/{program_id}/duration")
def set_program_duration(program_id: str, body: ProgramDuration, db: DBSession = Depends(get_db)) -> dict:
    program = db.get(LearningProgram, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="Not found")
    program.duration_months = body.duration_months
    program.version += 1
    db.commit()
    return {"ok": True, "version": program.version}
