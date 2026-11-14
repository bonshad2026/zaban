import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from zaban.admin import require_admin
from zaban.config import settings
from zaban.conversation.service import prompt_ttl_seconds
from zaban.services.ai_models import CHAT_MODELS
from zaban.db import get_db
from zaban.learning_aids import _progress_out
from zaban.models import (
    ConsultRequest,
    PlacementQuestion,
    WebSession,
    CooperationRequest,
    Guardian,
    LearnerDetails,
    Payment,
    SelfTest,
    Student,
    Tenant,
    TutorSession,
    Usage,
    utcnow,
)
from zaban.services.evaluation import past_evaluations
from zaban.services.learner_details import details_out
from zaban.services.settings_store import (
    EXPECTED_OUTPUT_KEY,
    PAYMENT_PROVIDER_KEY,
    PROMPT_MODE_DEFAULT,
    PROMPT_MODE_KEY,
    MODE_LABELS,
    PUBLIC_BASE_URL_KEY,
    PROMPT_TOKEN_TTL_KEY,
    AI_API_KEY_KEY,
    AI_BASE_URL_KEY,
    AI_MODEL_KEY,
    AI_PROVIDER_KEY,
    SMS_API_KEY_KEY,
    SMS_PROVIDER_KEY,
    SMS_TEMPLATE_KEY,
    ZARINPAL_MERCHANT_KEY,
    get_setting,
    set_setting,
)
from zaban.services.prompt_template import DEFAULT_TEMPLATE, PLACEHOLDERS, get_template, learner_values, render, save_template
from zaban.services.sms import sms_provider_for
from zaban.services.metering import session_usage
from zaban.services.payments import has_active_plan

# Everything the operator panel needs that is not part of the lesson itself.
router = APIRouter(prefix="/admin/api", dependencies=[Depends(require_admin)])



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
        "conversation_prompt_ttl_seconds": prompt_ttl_seconds(db),
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
    conversation_prompt_ttl_seconds: int | None = Field(default=None, ge=60, le=86400)


@router.post("/settings")
def save_settings(body: SettingsUpdate, db: DBSession = Depends(get_db)) -> dict:
    if body.prompt_mode is not None:
        set_setting(db, PROMPT_MODE_KEY, body.prompt_mode)
    if body.expected_output is not None:
        set_setting(db, EXPECTED_OUTPUT_KEY, body.expected_output.strip())
    if body.payment_provider is not None:
        set_setting(db, PAYMENT_PROVIDER_KEY, body.payment_provider)
    if body.conversation_prompt_ttl_seconds is not None:
        set_setting(db, PROMPT_TOKEN_TTL_KEY, str(body.conversation_prompt_ttl_seconds))
    db.commit()
    return {"ok": True}


def _mask(value: str) -> str:
    # Only the last four characters are shown, so the administrator can tell which key is stored.
    return f"••••{value[-4:]}" if len(value) > 4 else ("••••" if value else "")


@router.get("/connections")
def read_connections(db: DBSession = Depends(get_db)) -> dict:
    # Keys are returned masked. The panel never sends a full key back to the browser.
    sms_key = get_setting(db, SMS_API_KEY_KEY) or settings.kavenegar_api_key or ""
    merchant = get_setting(db, ZARINPAL_MERCHANT_KEY) or settings.zarinpal_merchant_id or ""
    # The address is saved in the database, so a new release or a restart does not change it. The environment is only the default.
    site = (get_setting(db, PUBLIC_BASE_URL_KEY) or settings.public_base_url).rstrip("/")
    return {
        "sms_provider": sms_provider_for(db),
        "sms_api_key_masked": _mask(sms_key),
        "sms_api_key_set": bool(sms_key),
        "sms_otp_template": get_setting(db, SMS_TEMPLATE_KEY, settings.kavenegar_otp_template or ""),
        "payment_provider": get_setting(db, PAYMENT_PROVIDER_KEY, settings.payment_gateway),
        "zarinpal_merchant_masked": _mask(merchant),
        "zarinpal_merchant_set": bool(merchant),
        "public_base_url": site,
        "callback_url": f"{site}/v1/web/billing/zarinpal/callback",
        "ai_provider": get_setting(db, AI_PROVIDER_KEY, settings.ai_provider),
        "ai_base_url": get_setting(db, AI_BASE_URL_KEY, settings.openai_base_url),
        "ai_model": get_setting(db, AI_MODEL_KEY, settings.model if settings.ai_provider != "openai" else settings.openai_model),
        "ai_model_catalog": CHAT_MODELS,
        "ai_api_key_set": bool(get_setting(db, AI_API_KEY_KEY, settings.anthropic_api_key or settings.openai_api_key or "")),
        "ai_api_key_masked": _mask(get_setting(db, AI_API_KEY_KEY, settings.anthropic_api_key or settings.openai_api_key or "")),
    }


class ConnectionsUpdate(BaseModel):
    # None means "leave as it is". An empty string clears a value, so the environment value applies again.
    sms_provider: str | None = Field(default=None, pattern=r"^(kavenegar|dev)$")
    sms_api_key: str | None = Field(default=None, max_length=200)
    sms_otp_template: str | None = Field(default=None, max_length=60)
    payment_provider: str | None = Field(default=None, pattern=r"^(fake|zarinpal)$")
    zarinpal_merchant_id: str | None = Field(default=None, max_length=100)
    public_base_url: str | None = Field(default=None, max_length=200)
    ai_provider: str | None = Field(default=None, pattern=r"^(anthropic|openai)$")
    ai_base_url: str | None = Field(default=None, max_length=200)
    ai_model: str | None = Field(default=None, max_length=120)
    ai_api_key: str | None = Field(default=None, max_length=300)


@router.post("/connections")
def save_connections(body: ConnectionsUpdate, db: DBSession = Depends(get_db)) -> dict:
    if body.sms_provider == "dev" and settings.environment == "production":
        raise HTTPException(status_code=400, detail="The development SMS sender cannot be used in production")
    if body.sms_provider is not None:
        set_setting(db, SMS_PROVIDER_KEY, body.sms_provider)
    if body.sms_api_key is not None and body.sms_api_key.strip():
        set_setting(db, SMS_API_KEY_KEY, body.sms_api_key.strip())
    if body.sms_otp_template is not None:
        set_setting(db, SMS_TEMPLATE_KEY, body.sms_otp_template.strip())
    if body.payment_provider is not None:
        set_setting(db, PAYMENT_PROVIDER_KEY, body.payment_provider)
    if body.zarinpal_merchant_id is not None and body.zarinpal_merchant_id.strip():
        set_setting(db, ZARINPAL_MERCHANT_KEY, body.zarinpal_merchant_id.strip())
    if body.ai_provider is not None:
        set_setting(db, AI_PROVIDER_KEY, body.ai_provider)
    if body.ai_base_url is not None:
        base = body.ai_base_url.strip().rstrip("/")
        if base and not re.fullmatch(r"https?://[^\s]+", base):
            raise HTTPException(status_code=400, detail="The AI address must start with http:// or https://")
        set_setting(db, AI_BASE_URL_KEY, base)
    if body.ai_model is not None:
        set_setting(db, AI_MODEL_KEY, body.ai_model.strip())
    if body.ai_api_key is not None and body.ai_api_key.strip():
        set_setting(db, AI_API_KEY_KEY, body.ai_api_key.strip())
    if body.public_base_url is not None:
        address = body.public_base_url.strip().rstrip("/")
        if address and not re.fullmatch(r"https?://[^\s/]+(/[^\s]*)?", address):
            raise HTTPException(status_code=400, detail="The site address must start with http:// or https://")
        set_setting(db, PUBLIC_BASE_URL_KEY, address)
    db.commit()
    return {"ok": True}


@router.get("/learners")
def list_learners(db: DBSession = Depends(get_db)) -> list[dict]:
    # Every learner, children of a parent included, so the panel can pick any of them by name.
    students = db.query(Student).order_by(Student.display_name).all()
    guardians = {g.id: g.full_name for g in db.query(Guardian).all()}
    return [
        {
            "id": s.id,
            "name": s.display_name or s.username or "—",
            "kind": "self" if s.self_owner_id else "child",
            "parent": guardians.get(s.guardian_id or s.self_owner_id, ""),
        }
        for s in students
    ]


def _lesson_rows(db: DBSession, student: Student) -> list[dict]:
    # Each lesson with its score, and the tokens and cost its replies used.
    lessons = (
        db.query(TutorSession)
        .filter(TutorSession.student_id == student.id)
        .order_by(TutorSession.started_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": s.id,
            "started_at": s.started_at.isoformat(),
            "status": s.status,
            "score": s.score,
            **session_usage(db, s.id),
        }
        for s in lessons
    ]


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
        "sessions": _lesson_rows(db, student),
    }


@router.get("/sessions")
def active_sessions(db: DBSession = Depends(get_db)) -> list[dict]:
    # Sign-ins that are still valid, grouped by the person. Each person has one entry with the list of their sign-ins.
    cutoff = utcnow() - timedelta(seconds=settings.web_session_ttl_seconds)
    rows = (
        db.query(WebSession)
        .filter(WebSession.revoked_at.is_(None), WebSession.created_at >= cutoff)
        .order_by(WebSession.created_at.desc())
        .limit(2000)
        .all()
    )
    groups: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row.role, row.subject_id)
        if key not in groups:
            if row.role == "guardian":
                person = db.get(Guardian, row.subject_id)
                name, contact = (person.full_name, person.phone) if person else ("", "")
            else:
                person = db.get(Student, row.subject_id)
                name, contact = (person.display_name, "پروفایل یادگیری خود بزرگسال") if person else ("", "")
            groups[key] = {"role": row.role, "subject_id": row.subject_id, "name": name, "contact": contact, "sessions": []}
        groups[key]["sessions"].append(
            {"id": row.id, "started_at": row.created_at.isoformat(), "user_agent": row.user_agent, "ip": row.ip}
        )
    return list(groups.values())


class SessionRevoke(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=500)


@router.post("/sessions/revoke")
def revoke_sessions(body: SessionRevoke, db: DBSession = Depends(get_db)) -> dict:
    # Ends the chosen sign-ins. Those devices must sign in again.
    count = (
        db.query(WebSession)
        .filter(WebSession.id.in_(body.ids), WebSession.revoked_at.is_(None))
        .update({"revoked_at": utcnow()}, synchronize_session=False)
    )
    db.commit()
    return {"revoked": count}


@router.get("/prompt-template")
def read_prompt_template(db: DBSession = Depends(get_db)) -> dict:
    return {
        "template": get_template(db),
        "default_template": DEFAULT_TEMPLATE,
        "placeholders": [{"key": key, "label": label} for key, label in PLACEHOLDERS],
    }


class PromptTemplateUpdate(BaseModel):
    template: str = Field(min_length=1, max_length=8000)


@router.post("/prompt-template")
def write_prompt_template(body: PromptTemplateUpdate, db: DBSession = Depends(get_db)) -> dict:
    save_template(db, body.template)
    return {"ok": True}


class PromptGenerate(BaseModel):
    student_id: str = Field(min_length=1, max_length=32)


@router.post("/prompt/generate")
def generate_prompt(body: PromptGenerate, db: DBSession = Depends(get_db)) -> dict:
    # The template is filled with stored values only. Placeholders that have no value are returned, so the administrator can fix them.
    student = db.get(Student, body.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Not found")
    text, unknown = render(get_template(db), learner_values(db, student))
    return {"prompt": text, "unknown_placeholders": unknown}


class PlacementQuestionIn(BaseModel):
    skill: str = Field(pattern=r"^(reading|grammar|listening)$")
    level: str = Field(pattern=r"^(A1|A2|B1|B2|C1)$")
    text: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=6)
    answer: int = Field(ge=0, le=5)
    audio_text: str = Field(default="", max_length=1000)
    active: bool = True


def _question_out(q: PlacementQuestion) -> dict:
    import json as _json

    return {
        "id": q.id,
        "skill": q.skill,
        "level": q.level,
        "text": q.text,
        "options": _json.loads(q.options),
        "answer": q.answer,
        "audio_text": q.audio_text or "",
        "active": bool(q.active),
    }


@router.get("/placement-questions")
def list_placement_questions(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(PlacementQuestion).order_by(PlacementQuestion.skill, PlacementQuestion.level, PlacementQuestion.id).all()
    return [_question_out(q) for q in rows]


@router.post("/placement-questions", status_code=201)
def add_placement_question(body: PlacementQuestionIn, db: DBSession = Depends(get_db)) -> dict:
    import json as _json

    if body.answer >= len(body.options):
        raise HTTPException(status_code=400, detail="The correct answer must be one of the options")
    q = PlacementQuestion(skill=body.skill, level=body.level, text=body.text.strip(), options=_json.dumps(body.options),
                          answer=body.answer, audio_text=body.audio_text.strip(), active=body.active)
    db.add(q)
    db.commit()
    return _question_out(q)


@router.post("/placement-questions/{question_id}")
def update_placement_question(question_id: int, body: PlacementQuestionIn, db: DBSession = Depends(get_db)) -> dict:
    import json as _json

    q = db.get(PlacementQuestion, question_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Not found")
    if body.answer >= len(body.options):
        raise HTTPException(status_code=400, detail="The correct answer must be one of the options")
    q.skill, q.level, q.text = body.skill, body.level, body.text.strip()
    q.options, q.answer = _json.dumps(body.options), body.answer
    q.audio_text, q.active = body.audio_text.strip(), body.active
    db.commit()
    return _question_out(q)

