import base64
import hmac
from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from zaban.config import settings
from zaban.db import get_db
from zaban.models import (
    BillingPlan,
    ConsultRequest,
    CurriculumVariant,
    Guardian,
    Payment,
    Student,
    TutorProfile,
    LearningProgram,
    ProgramItem,
    StudentProgress,
    VoiceSample,
)
from zaban.services.learner import get_global_prompt, set_global_prompt, set_learner_profile
from zaban.schemas import VoiceSampleCreate
from zaban.services.payments import confirm_payment
from zaban.program_data import GOALS
from zaban.services.programs import approve_block
from zaban.services.curriculum import (
    bump_catalog_version,
    catalog_version,
    catalog_view,
    create_variant,
    save_variant_text,
)

# Operator page. One shared password from the environment (ADMIN_PASSWORD). Sessions last 12 hours.
router = APIRouter(prefix="/admin/api")

ADMIN_COOKIE = "zaban_admin"
ADMIN_TTL_SECONDS = 12 * 60 * 60
_admin_serializer = URLSafeTimedSerializer(settings.secret_key, salt="admin-session")


def require_admin(token: str | None = Cookie(default=None, alias=ADMIN_COOKIE)) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Please sign in")
    try:
        _admin_serializer.loads(token, max_age=ADMIN_TTL_SECONDS)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Please sign in")


class AdminLogin(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class StatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(new|contacted|closed)$")


class PaymentDecision(BaseModel):
    ok: bool


class PlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=300)
    price_toman: int = Field(ge=0)
    days: int = Field(ge=1, le=3650)


class PlanUpdate(BaseModel):
    active: bool


class ProfileUpdate(BaseModel):
    interests: str = Field(default="", max_length=300)
    motivation: str = Field(default="", max_length=60)
    instructions: str = Field(default="", max_length=2000)


class GlobalPromptUpdate(BaseModel):
    text: str = Field(default="", max_length=4000)


@router.post("/login")
def admin_login(body: AdminLogin, response: Response) -> dict:
    if not settings.admin_password:
        raise HTTPException(status_code=503, detail="The admin page is not configured")
    if not hmac.compare_digest(body.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="Wrong password")
    token = _admin_serializer.dumps({"adm": True})
    response.set_cookie(
        ADMIN_COOKIE,
        token,
        max_age=ADMIN_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        secure=settings.environment == "production",
        path="/",
    )
    return {"ok": True}


@router.post("/logout")
def admin_logout(response: Response) -> dict:
    response.delete_cookie(ADMIN_COOKIE, path="/")
    return {"ok": True}


@router.get("/consults", dependencies=[Depends(require_admin)])
def list_consults(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(ConsultRequest).order_by(ConsultRequest.created_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "phone": r.phone,
            "message": r.message,
            "preferred_time": r.preferred_time,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/consults/{consult_id}/status", dependencies=[Depends(require_admin)])
def update_consult(consult_id: int, body: StatusUpdate, db: DBSession = Depends(get_db)) -> dict:
    item = db.get(ConsultRequest, consult_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    item.status = body.status
    db.commit()
    return {"ok": True}


@router.get("/adults", dependencies=[Depends(require_admin)])
def list_adults(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(Guardian).order_by(Guardian.created_at.desc()).limit(300).all()
    out = []
    for g in rows:
        # The plan type comes from the latest confirmed payment, since that is what extended the period.
        last = (
            db.query(Payment)
            .filter(Payment.guardian_id == g.id, Payment.status == "confirmed")
            .order_by(Payment.confirmed_at.desc())
            .first()
        )
        plan = db.get(BillingPlan, last.plan_id) if last else None
        out.append(
            {
                "id": g.id,
                "name": g.full_name,
                "phone": g.phone,
                "goal": g.goal,
                "plan_name": plan.name if plan else None,
                "plan_expires_at": g.plan_expires_at.isoformat() if g.plan_expires_at else None,
                "created_at": g.created_at.isoformat(),
            }
        )
    return out


# "paid" lists payments the buyer has paid and that wait for the administrator's decision.
@router.get("/payments", dependencies=[Depends(require_admin)])
def list_payments(status: str = "paid", db: DBSession = Depends(get_db)) -> list[dict]:
    query = db.query(Payment).order_by(Payment.created_at.desc())
    if status != "all":
        query = query.filter(Payment.status == status)
    out = []
    for p in query.limit(200).all():
        guardian = db.get(Guardian, p.guardian_id)
        plan = db.get(BillingPlan, p.plan_id)
        out.append(
            {
                "id": p.id,
                "adult": guardian.full_name if guardian else "",
                "phone": guardian.phone if guardian else "",
                "plan": plan.name if plan else "",
                "days": plan.days if plan else 0,
                "amount_toman": p.amount_toman,
                "status": p.status,
                "gateway": p.gateway,
                "created_at": p.created_at.isoformat(),
            }
        )
    return out


@router.post("/payments/{payment_id}/decision", dependencies=[Depends(require_admin)])
def decide_payment(payment_id: str, body: PaymentDecision, db: DBSession = Depends(get_db)) -> dict:
    # For payments the gateway could not report back. Confirming here follows the same rule as a gateway callback.
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Not found")
    confirm_payment(db, payment, body.ok)
    return {"status": payment.status}


@router.get("/plans", dependencies=[Depends(require_admin)])
def list_plans(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(BillingPlan).order_by(BillingPlan.price_toman).all()
    return [
        {"id": p.id, "name": p.name, "description": p.description, "price_toman": p.price_toman, "days": p.days, "active": p.active}
        for p in rows
    ]


@router.post("/plans", status_code=201, dependencies=[Depends(require_admin)])
def create_plan(body: PlanCreate, db: DBSession = Depends(get_db)) -> dict:
    plan = BillingPlan(name=body.name.strip(), description=body.description.strip(), price_toman=body.price_toman, days=body.days)
    db.add(plan)
    db.commit()
    return {"id": plan.id}


@router.post("/plans/{plan_id}/active", dependencies=[Depends(require_admin)])
def set_plan_active(plan_id: str, body: PlanUpdate, db: DBSession = Depends(get_db)) -> dict:
    plan = db.get(BillingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Not found")
    plan.active = body.active
    db.commit()
    return {"ok": True}


@router.get("/students", dependencies=[Depends(require_admin)])
def list_students(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(Student).order_by(Student.created_at.desc()).limit(300).all()
    profiles = {p.student_id: p for p in db.query(TutorProfile).all()}
    return [
        {
            "id": s.id,
            "name": s.display_name,
            "kind": "self" if s.self_owner_id else "child",
            "username": s.username,
            "age_band": s.age_band,
            "cefr_level": s.cefr_level,
            "interests": profiles[s.id].interests if s.id in profiles else "",
            "motivation": profiles[s.id].motivation if s.id in profiles else "",
            "instructions": profiles[s.id].instructions if s.id in profiles else "",
        }
        for s in rows
    ]


# The facts and notes the lesson prompt is built from. Empty values clear them.
@router.post("/students/{student_id}/profile", dependencies=[Depends(require_admin)])
def save_profile(student_id: str, body: ProfileUpdate, db: DBSession = Depends(get_db)) -> dict:
    if db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="Not found")
    set_learner_profile(
        db,
        student_id,
        interests=body.interests,
        motivation=body.motivation,
        instructions=body.instructions,
    )
    db.commit()
    return {"ok": True}


# The general prompt that every lesson uses, before the learner's own details.
@router.get("/global-prompt", dependencies=[Depends(require_admin)])
def read_global_prompt(db: DBSession = Depends(get_db)) -> dict:
    return {"text": get_global_prompt(db)}


@router.post("/global-prompt", dependencies=[Depends(require_admin)])
def write_global_prompt(body: GlobalPromptUpdate, db: DBSession = Depends(get_db)) -> dict:
    set_global_prompt(db, body.text.strip())
    db.commit()
    return {"ok": True}


MAX_SAMPLE_BYTES = 3 * 1024 * 1024


@router.get("/voice-samples", dependencies=[Depends(require_admin)])
def list_voice_samples(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(VoiceSample).order_by(VoiceSample.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "accent": s.accent,
            "mime": s.mime,
            "size_bytes": len(s.data),
            "created_at": s.created_at.isoformat(),
        }
        for s in rows
    ]


@router.post("/voice-samples", status_code=201, dependencies=[Depends(require_admin)])
def add_voice_sample(body: VoiceSampleCreate, db: DBSession = Depends(get_db)) -> dict:
    try:
        data = base64.b64decode(body.data_base64, validate=True)
    except ValueError:
        raise HTTPException(status_code=400, detail="The file could not be read")
    if not data:
        raise HTTPException(status_code=400, detail="The file is empty")
    if len(data) > MAX_SAMPLE_BYTES:
        raise HTTPException(status_code=413, detail="The file is too large. Use a file under 3 MB")
    sample = VoiceSample(name=body.name.strip(), accent=body.accent, mime=body.mime, data=data)
    db.add(sample)
    db.commit()
    return {"id": sample.id}


@router.delete("/voice-samples/{sample_id}", dependencies=[Depends(require_admin)])
def delete_voice_sample(sample_id: str, db: DBSession = Depends(get_db)) -> dict:
    sample = db.get(VoiceSample, sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(sample)
    db.commit()
    return {"ok": True}


# ----- Curriculum: the topics, the written versions, and the slots still empty -----

class VariantSave(BaseModel):
    opener: str = Field(default="", max_length=300)
    phrases: list[str] = Field(default_factory=list, max_length=8)
    style: str = Field(default="", max_length=200)


class VariantCreate(VariantSave):
    topic_id: str = Field(min_length=1, max_length=40)
    band: Literal["K", "J", "T", "S", "A"]
    level: Literal["A1", "A2", "B1", "B2", "C1", "C2"]


@router.get("/curriculum", dependencies=[Depends(require_admin)])
def read_curriculum(db: DBSession = Depends(get_db)) -> dict:
    return catalog_view(db)


@router.put("/curriculum/variants/{variant_id}", dependencies=[Depends(require_admin)])
def save_variant(variant_id: str, body: VariantSave, db: DBSession = Depends(get_db)) -> dict:
    variant = db.get(CurriculumVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="Not found")
    save_variant_text(variant, body.opener, body.phrases, body.style)
    bump_catalog_version(db)
    db.commit()
    return {"ok": True, "version": catalog_version(db)}


@router.post("/curriculum/variants", status_code=201, dependencies=[Depends(require_admin)])
def add_variant(body: VariantCreate, db: DBSession = Depends(get_db)) -> dict:
    variant_id = f"{body.topic_id}.{body.band}.{body.level}"
    if db.get(CurriculumVariant, variant_id) is not None:
        raise HTTPException(status_code=409, detail="This version already exists")
    variant = create_variant(db, body.topic_id, body.band, body.level)
    if variant is None:
        raise HTTPException(status_code=400, detail="This topic does not cover that age band or level")
    save_variant_text(variant, body.opener, body.phrases, body.style)
    bump_catalog_version(db)
    db.commit()
    return {"id": variant.id, "version": catalog_version(db)}


# ----- Learning programs: the lessons in order, with their text. Edits are saved in the database. -----

class ProgramItemSave(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    activity: str = Field(default="", max_length=600)
    phrases: list[str] = Field(default_factory=list, max_length=12)


@router.get("/programs", dependencies=[Depends(require_admin)])
def list_programs(db: DBSession = Depends(get_db)) -> dict:
    programs = []
    for program in db.query(LearningProgram).order_by(LearningProgram.id).all():
        items = (
            db.query(ProgramItem)
            .filter(ProgramItem.program_id == program.id)
            .order_by(ProgramItem.position)
            .all()
        )
        programs.append(
            {
                "id": program.id,
                "name": program.name,
                "band": program.band,
                "level": program.level,
                "goal": program.goal,
                "block_size": program.block_size,
                "version": program.version,
                "items": [
                    {"position": i.position + 1, "title": i.title, "activity": i.activity, "phrases": i.phrases}
                    for i in items
                ],
            }
        )
    return {"goals": [{"key": k, "label": label} for k, label in GOALS], "programs": programs}


@router.put("/programs/{program_id}/items/{number}", dependencies=[Depends(require_admin)])
def save_program_item(program_id: str, number: int, body: ProgramItemSave, db: DBSession = Depends(get_db)) -> dict:
    # number is the lesson number as the administrator sees it (1 is the first lesson).
    item = (
        db.query(ProgramItem)
        .filter(ProgramItem.program_id == program_id, ProgramItem.position == number - 1)
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    item.title = body.title.strip()
    item.activity = body.activity.strip()
    item.phrases = [p.strip() for p in body.phrases if p.strip()]
    program = db.get(LearningProgram, program_id)
    program.version += 1
    db.commit()
    return {"ok": True, "version": program.version}


@router.post("/students/{student_id}/resume-program", dependencies=[Depends(require_admin)])
def resume_program(student_id: str, db: DBSession = Depends(get_db)) -> dict:
    # Approves the next block of lessons after a block has finished.
    progress = db.get(StudentProgress, student_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Not found")
    approve_block(progress)
    db.commit()
    return {"status": progress.status}


@router.get("/program-approvals", dependencies=[Depends(require_admin)])
def list_program_approvals(db: DBSession = Depends(get_db)) -> list[dict]:
    # Learners whose block of lessons is finished and waits for approval to continue.
    rows = db.query(StudentProgress).filter(StudentProgress.status == "waiting_approval").all()
    out = []
    for progress in rows:
        student = db.get(Student, progress.student_id)
        program = db.get(LearningProgram, progress.program_id)
        out.append(
            {
                "student_id": progress.student_id,
                "name": student.display_name if student else "",
                "program": program.name if program else "",
                "done": progress.position,
            }
        )
    return out
