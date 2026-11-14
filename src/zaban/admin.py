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
    AppSetting,
    BillingPlan,
    ConsultRequest,
    CooperationRequest,
    CurriculumPoint,
    CurriculumTopic,
    CurriculumVariant,
    HelpFacet,
    HelpTag,
    Guardian,
    HelpContent,
    LearnerDetails,
    Payment,
    Plan,
    Student,
    TutorProfile,
    VoiceSample,
)
from zaban.services.evaluation import course_note, past_evaluations
from zaban.services.help_content import delete_facet, delete_tag, facet_tree, set_content_tags, tags_by_content
from zaban.services.learner import get_accent, get_global_prompt, set_global_prompt, set_learner_profile
from zaban.services.settings_store import EXPECTED_OUTPUT_KEY, PROMPT_MODE_DEFAULT, PROMPT_MODE_KEY, get_setting, set_setting
from zaban.services.sessions import compose_start_prompt, join_prompt
from zaban.schemas import HelpContentCreate, VoiceSampleCreate
from zaban.services.self_test_prompt import (
    DEFAULT_RULES,
    RULE_KEY,
    build_prompt,
    get_template,
    placeholders,
    save_rules,
    save_template,
    stored_rules,
    DEFAULT_TEMPLATE as DEFAULT_SELF_TEST_TEMPLATE,
)
from zaban.services.payments import confirm_payment
from zaban.services.curriculum import (
    choose_topic,
    topic_note,
    ordered_topics,
    set_topic_order,
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


# Every admin sign-in carries the version that was current when it started. «Sign out everywhere» raises the version,
# so every older sign-in stops working at once, on every device.
ADMIN_VERSION_KEY = "admin_session_version"


def _admin_version(db: DBSession) -> int:
    value = get_setting(db, ADMIN_VERSION_KEY)
    return int(value) if value else 1


def require_admin(
    token: str | None = Cookie(default=None, alias=ADMIN_COOKIE),
    db: DBSession = Depends(get_db),
) -> None:
    if not token:
        raise HTTPException(status_code=401, detail="Please sign in")
    try:
        payload = _admin_serializer.loads(token, max_age=ADMIN_TTL_SECONDS)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Please sign in")
    if payload.get("v", 1) != _admin_version(db):
        raise HTTPException(status_code=401, detail="Please sign in")


class AdminLogin(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class StatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(new|reviewed|called|recall|awaiting_reply|contacted|closed)$")


class PaymentDecision(BaseModel):
    ok: bool


class PlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    name_en: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=300)
    price_toman: int = Field(ge=0)
    days: int = Field(ge=1, le=3650)
    token_allowance: int = Field(default=1_000_000, ge=1_000, le=1_000_000_000)


class PlanUpdate(BaseModel):
    active: bool


class ProfileUpdate(BaseModel):
    interests: str = Field(default="", max_length=300)
    motivation: str = Field(default="", max_length=60)
    instructions: str = Field(default="", max_length=2000)


class GlobalPromptUpdate(BaseModel):
    text: str = Field(default="", max_length=4000)


@router.post("/login")
def admin_login(body: AdminLogin, response: Response, db: DBSession = Depends(get_db)) -> dict:
    if not settings.admin_password:
        raise HTTPException(status_code=503, detail="The admin page is not configured")
    if not hmac.compare_digest(body.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="Wrong password")
    token = _admin_serializer.dumps({"adm": True, "v": _admin_version(db)})
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


@router.post("/logout-all", dependencies=[Depends(require_admin)])
def admin_logout_everywhere(response: Response, db: DBSession = Depends(get_db)) -> dict:
    # Ends the admin sign-in on every device, this one included.
    set_setting(db, ADMIN_VERSION_KEY, str(_admin_version(db) + 1))
    db.commit()
    response.delete_cookie(ADMIN_COOKIE, path="/")
    return {"ok": True}


@router.get("/consults", dependencies=[Depends(require_admin)])
def list_consults(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(ConsultRequest).order_by(ConsultRequest.created_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "last_name": r.last_name,
            "subject": r.subject,
            "contact_permission": r.contact_permission,
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
                "suspended": bool(g.suspended),
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
        {"id": p.id, "name": p.name, "name_en": p.name_en or "", "description": p.description, "price_toman": p.price_toman, "days": p.days, "token_allowance": p.token_allowance, "active": p.active}
        for p in rows
    ]


@router.post("/plans", status_code=201, dependencies=[Depends(require_admin)])
def create_plan(body: PlanCreate, db: DBSession = Depends(get_db)) -> dict:
    plan = BillingPlan(
        name=body.name.strip(),
        name_en=body.name_en.strip() or None,
        description=body.description.strip(),
        token_allowance=body.token_allowance,
        price_toman=body.price_toman,
        days=body.days,
    )
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


@router.delete("/plans/{plan_id}", dependencies=[Depends(require_admin)])
def delete_plan(plan_id: str, db: DBSession = Depends(get_db)) -> dict:
    # A plan that payments refer to stays, so the history reads correctly. It can be switched off instead.
    plan = db.get(BillingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Not found")
    if db.query(Payment).filter(Payment.plan_id == plan.id).first() is not None:
        raise HTTPException(status_code=409, detail="این پلن پرداخت ثبت‌شده دارد و حذف نمی‌شود. به‌جای آن غیرفعالش کنید.")
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.get("/students", dependencies=[Depends(require_admin)])
def list_students(db: DBSession = Depends(get_db)) -> list[dict]:
    # Children created on the website are not listed. Self learners and tenant API students are.
    rows = db.query(Student).filter(Student.guardian_id.is_(None)).order_by(Student.created_at.desc()).limit(300).all()
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


# The prompt a lesson for this learner would start with, built from the same sources as a real lesson.
# The parts are returned one by one, so the administrator can see where each sentence comes from.
@router.get("/students/{student_id}/start-prompt", dependencies=[Depends(require_admin)])
def preview_start_prompt(student_id: str, db: DBSession = Depends(get_db)) -> dict:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Not found")
    plan = (
        db.query(Plan)
        .filter(Plan.student_id == student.id, Plan.status == "active")
        .order_by(Plan.start_date.desc())
        .first()
    )
    # The lesson the preview shows: the topic the next lesson would use.
    chosen = choose_topic(db, student)
    lesson = topic_note(*chosen) if chosen else ""
    parts = compose_start_prompt(
        student,
        plan,
        10,
        get_global_prompt(db),
        db.get(TutorProfile, student.id),
        get_accent(db, student.id),
        lesson,
        details=db.get(LearnerDetails, student.id),
        mode=get_setting(db, PROMPT_MODE_KEY, PROMPT_MODE_DEFAULT),
        expected_output=get_setting(db, EXPECTED_OUTPUT_KEY),
        past_notes=past_evaluations(db, student.id),
        course_note=course_note(db, student),
    )
    return {"parts": parts, "prompt": join_prompt(parts)}


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


class TopicSave(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(default="", max_length=3000)


class PointCreate(BaseModel):
    text: str = Field(min_length=1, max_length=300)


@router.get("/curriculum/topics", dependencies=[Depends(require_admin)])
def list_curriculum_topics(db: DBSession = Depends(get_db)) -> list[dict]:
    # The topic, its conversation goal and the points to talk about. Bands, levels and versions are not shown here.
    topics = ordered_topics(db)
    points = db.query(CurriculumPoint).order_by(CurriculumPoint.sort_order, CurriculumPoint.created_at).all()
    by_topic: dict[str, list[dict]] = {}
    for point in points:
        by_topic.setdefault(point.topic_id, []).append({"id": point.id, "text": point.text})
    return [
        {"id": t.id, "title": t.title, "goal": t.goal, "points": by_topic.get(t.id, [])}
        for t in topics
    ]


class TopicOrder(BaseModel):
    # Every topic id in the lesson order, as dragged in the panel.
    ids: list[str] = Field(min_length=1, max_length=500)


@router.put("/curriculum/order", dependencies=[Depends(require_admin)])
def save_topic_order(body: TopicOrder, db: DBSession = Depends(get_db)) -> dict:
    known = {row[0] for row in db.query(CurriculumTopic.id).all()}
    unknown = [tid for tid in body.ids if tid not in known]
    if unknown:
        raise HTTPException(status_code=404, detail="Unknown topic")
    set_topic_order(db, body.ids)
    return {"ok": True}


@router.put("/curriculum/topics/{topic_id}", dependencies=[Depends(require_admin)])
def save_curriculum_topic(topic_id: str, body: TopicSave, db: DBSession = Depends(get_db)) -> dict:
    topic = db.get(CurriculumTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Not found")
    topic.title = body.title.strip()
    topic.goal = body.goal.strip()
    bump_catalog_version(db)
    db.commit()
    return {"ok": True, "version": catalog_version(db)}


@router.post("/curriculum/topics/{topic_id}/points", status_code=201, dependencies=[Depends(require_admin)])
def add_curriculum_point(topic_id: str, body: PointCreate, db: DBSession = Depends(get_db)) -> dict:
    if db.get(CurriculumTopic, topic_id) is None:
        raise HTTPException(status_code=404, detail="Not found")
    order = db.query(CurriculumPoint).filter(CurriculumPoint.topic_id == topic_id).count()
    point = CurriculumPoint(topic_id=topic_id, text=body.text.strip(), sort_order=order)
    db.add(point)
    db.commit()
    return {"id": point.id}


@router.delete("/curriculum/points/{point_id}", dependencies=[Depends(require_admin)])
def remove_curriculum_point(point_id: str, db: DBSession = Depends(get_db)) -> dict:
    point = db.get(CurriculumPoint, point_id)
    if point is None:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(point)
    db.commit()
    return {"ok": True}


# ----- Cooperation requests (people who want to work with the company, not learners) -----

COOPERATION_STATUSES = r"^(new|contacted|closed)$"


class CooperationStatus(BaseModel):
    status: str = Field(pattern=COOPERATION_STATUSES)


@router.get("/cooperations", dependencies=[Depends(require_admin)])
def list_cooperations(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(CooperationRequest).order_by(CooperationRequest.created_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "subject": r.subject,
            "phone": r.phone,
            "email": r.email,
            "message": r.message,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/cooperations/{item_id}/status", dependencies=[Depends(require_admin)])
def update_cooperation(item_id: int, body: CooperationStatus, db: DBSession = Depends(get_db)) -> dict:
    item = db.get(CooperationRequest, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    item.status = body.status
    db.commit()
    return {"ok": True}


# ----- Help content: podcasts, stories, animations, videos and samples -----

@router.get("/help-content", dependencies=[Depends(require_admin)])
def list_help_content(db: DBSession = Depends(get_db)) -> list[dict]:
    rows = db.query(HelpContent).order_by(HelpContent.created_at.desc()).all()
    tags = tags_by_content(db, [h.id for h in rows])
    return [
        {
            "id": h.id,
            "title": h.title,
            "category": h.category,
            "age_band": h.age_band,
            "level": h.level,
            "gender": h.gender,
            "interests": h.interests,
            "tags": [{"id": t.id, "label": t.label} for t in tags.get(h.id, [])],
            "topic_id": h.topic_id,
            "stage": h.stage,
            "url": h.url,
            "mime": h.mime,
            "size_bytes": len(h.data) if h.data else 0,
        }
        for h in rows
    ]


@router.post("/help-content", status_code=201, dependencies=[Depends(require_admin)])
def add_help_content(body: HelpContentCreate, db: DBSession = Depends(get_db)) -> dict:
    data = None
    if body.data_base64 is not None:
        try:
            data = base64.b64decode(body.data_base64, validate=True)
        except ValueError:
            raise HTTPException(status_code=400, detail="The file could not be read")
        if not data:
            raise HTTPException(status_code=400, detail="The file is empty")
        if len(data) > MAX_SAMPLE_BYTES:
            raise HTTPException(status_code=413, detail="The file is too large. Use a file under 3 MB")
    item = HelpContent(
        title=body.title.strip(),
        category=body.category,
        age_band=body.age_band,
        level=body.level,
        gender=body.gender,
        interests=body.interests.strip(),
        topic_id=body.topic_id,
        stage=(body.stage or "").strip() or None,
        url=body.url,
        mime=body.mime,
        data=data,
    )
    db.add(item)
    set_content_tags(db, item, body.tag_ids)
    db.commit()
    return {"id": item.id}


class HelpClassification(BaseModel):
    # The learner rules use the age band and the level, so they are required. Gender empty means for everyone.
    age_band: Literal["K", "J", "T", "S", "A"]
    level: Literal["A1", "A2", "B1", "B2", "C1", "C2"]
    gender: Literal["female", "male"] | None = None
    tag_ids: list[str] = Field(default_factory=list, max_length=50)


@router.put("/help-content/{item_id}/classification", dependencies=[Depends(require_admin)])
def update_help_classification(item_id: str, body: HelpClassification, db: DBSession = Depends(get_db)) -> dict:
    item = db.get(HelpContent, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    item.age_band = body.age_band
    item.level = body.level
    item.gender = body.gender
    set_content_tags(db, item, body.tag_ids)
    db.commit()
    return {"ok": True}


class FacetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class TagCreate(BaseModel):
    label: str = Field(min_length=1, max_length=60)


@router.get("/help-facets", dependencies=[Depends(require_admin)])
def list_help_facets(db: DBSession = Depends(get_db)) -> list[dict]:
    return facet_tree(db)


@router.post("/help-facets", status_code=201, dependencies=[Depends(require_admin)])
def add_help_facet(body: FacetCreate, db: DBSession = Depends(get_db)) -> dict:
    facet = HelpFacet(name=body.name.strip(), sort_order=db.query(HelpFacet).count())
    db.add(facet)
    db.commit()
    return {"id": facet.id}


@router.delete("/help-facets/{facet_id}", dependencies=[Depends(require_admin)])
def remove_help_facet(facet_id: str, db: DBSession = Depends(get_db)) -> dict:
    if not delete_facet(db, facet_id):
        raise HTTPException(status_code=404, detail="Not found")
    db.commit()
    return {"ok": True}


@router.post("/help-facets/{facet_id}/tags", status_code=201, dependencies=[Depends(require_admin)])
def add_help_tag(facet_id: str, body: TagCreate, db: DBSession = Depends(get_db)) -> dict:
    facet = db.get(HelpFacet, facet_id)
    if facet is None:
        raise HTTPException(status_code=404, detail="Not found")
    tag = HelpTag(facet_id=facet.id, label=body.label.strip(), sort_order=len(facet.tags))
    db.add(tag)
    db.commit()
    return {"id": tag.id}


@router.delete("/help-tags/{tag_id}", dependencies=[Depends(require_admin)])
def remove_help_tag(tag_id: str, db: DBSession = Depends(get_db)) -> dict:
    if not delete_tag(db, tag_id):
        raise HTTPException(status_code=404, detail="Not found")
    db.commit()
    return {"ok": True}


@router.delete("/help-content/{item_id}", dependencies=[Depends(require_admin)])
def delete_help_content(item_id: str, db: DBSession = Depends(get_db)) -> dict:
    item = db.get(HelpContent, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


# ----- Self-test prompt: the admin can replace the base text used for every test -----

class SelfTestTemplate(BaseModel):
    template: str = Field(min_length=1, max_length=8000)


class SelfTestRule(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=1500)


class SelfTestPreview(BaseModel):
    student_id: str = Field(min_length=1, max_length=32)
    kind: Literal["qa", "conversation", "mixed", "suggested"]
    skill: Literal["writing", "listening", "speaking", "mixed"]
    minutes: Literal[5, 10, 15, 20, 30]


def _rules_out(db: DBSession) -> list[dict]:
    current = stored_rules(db)
    return [{"key": k, "text": v, "default": k in DEFAULT_RULES} for k, v in current.items()]


@router.get("/self-test/template", dependencies=[Depends(require_admin)])
def read_self_test_template(db: DBSession = Depends(get_db)) -> dict:
    return {
        "template": get_template(db),
        "default_template": DEFAULT_SELF_TEST_TEMPLATE,
        "placeholders": placeholders(db),
        "rules": _rules_out(db),
    }


@router.post("/self-test/template", dependencies=[Depends(require_admin)])
def write_self_test_template(body: SelfTestTemplate, db: DBSession = Depends(get_db)) -> dict:
    save_template(db, body.template)
    return {"ok": True}


@router.post("/self-test/rules", dependencies=[Depends(require_admin)])
def write_self_test_rule(body: SelfTestRule, db: DBSession = Depends(get_db)) -> dict:
    # A rule can be added under any key that matches the pattern. Its placeholder is {{rule.<key>}}.
    key = body.key.strip()
    if not RULE_KEY.match(key):
        raise HTTPException(status_code=422, detail="Use lowercase letters, digits and one dot, such as kind.quiz")
    rules = stored_rules(db)
    rules[key] = body.text.strip()
    save_rules(db, rules)
    return {"ok": True}


@router.delete("/self-test/rules/{key}", dependencies=[Depends(require_admin)])
def remove_self_test_rule(key: str, db: DBSession = Depends(get_db)) -> dict:
    # A default rule goes back to its default text. A rule the administrator added is removed.
    rules = stored_rules(db)
    if key not in rules:
        raise HTTPException(status_code=404, detail="Not found")
    if key in DEFAULT_RULES:
        rules[key] = DEFAULT_RULES[key]
    else:
        del rules[key]
    save_rules(db, rules)
    return {"ok": True}


@router.post("/self-test/preview", dependencies=[Depends(require_admin)])
def preview_self_test_prompt(body: SelfTestPreview, db: DBSession = Depends(get_db)) -> dict:
    # The prompt a self-test would start with for this learner. Nothing is saved.
    student = db.get(Student, body.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Not found")
    from zaban.services.curriculum import DEFAULT_LEVEL
    from zaban.services.self_test import choose_kind

    level = student.cefr_level or DEFAULT_LEVEL
    text, unknown = build_prompt(db, student, body.kind, choose_kind(body.kind, level), body.skill, body.minutes, level)
    return {"prompt": text, "unknown_placeholders": unknown}


class SuspensionUpdate(BaseModel):
    suspended: bool


@router.post("/adults/{adult_id}/suspension")
def set_suspension(adult_id: str, body: SuspensionUpdate, db: DBSession = Depends(get_db)) -> dict:
    # Suspending ends every sign-in of the adult and of their learner profile at once.
    guardian = db.get(Guardian, adult_id)
    if guardian is None:
        raise HTTPException(status_code=404, detail="Not found")
    guardian.suspended = body.suspended
    if body.suspended:
        ids = [guardian.id] + [s.id for s in db.query(Student).filter(Student.self_owner_id == guardian.id).all()]
        db.query(WebSession).filter(WebSession.subject_id.in_(ids), WebSession.revoked_at.is_(None)).update(
            {"revoked_at": utcnow()}, synchronize_session=False
        )
    db.commit()
    return {"suspended": guardian.suspended}


class PlanEdit(BaseModel):
    # Every field is optional. Only the fields that are sent change.
    name: str | None = Field(default=None, min_length=2, max_length=80)
    name_en: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    price_toman: int | None = Field(default=None, ge=0)
    days: int | None = Field(default=None, ge=1, le=3650)
    token_allowance: int | None = Field(default=None, ge=1_000, le=1_000_000_000)


@router.post("/plans/{plan_id}/update", dependencies=[Depends(require_admin)])
def update_plan(plan_id: str, body: PlanEdit, db: DBSession = Depends(get_db)) -> dict:
    plan = db.get(BillingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Not found")
    sent = body.model_dump(exclude_unset=True)
    for key, value in sent.items():
        if value is None:
            continue
        if key == "name_en":
            value = value.strip() or None
        elif isinstance(value, str):
            value = value.strip()
        setattr(plan, key, value)
    db.commit()
    return {"ok": True}

