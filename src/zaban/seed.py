from sqlalchemy.orm import Session

from datetime import timedelta

from zaban.config import Settings
from zaban.models import BillingPlan, Consent, Guardian, Student, Tenant, utcnow
from zaban.security import hash_api_key
from zaban.services.otp import normalize_phone
from zaban.services.passwords import hash_password

# Development prices. The real prices are set by the company, not in code.
DEMO_PLAN_NAMES_EN = {"مقدماتی (نمونه)": "Basic (sample)", "پیشرفته (نمونه)": "Advanced (sample)"}
DEMO_PLANS = [
    ("مقدماتی (نمونه)", "نمونه برای آزمایش", 1_000_000, 30),
    ("پیشرفته (نمونه)", "نمونه برای آزمایش", 2_000_000, 90),
]


def seed_demo_plans(db: Session) -> None:
    """Create sample plans for local development. Does nothing when plans already exist."""
    if db.query(BillingPlan).first() is not None:
        return
    for name, description, price, days in DEMO_PLANS:
        db.add(BillingPlan(name=name, name_en=DEMO_PLAN_NAMES_EN.get(name), description=description, price_toman=price, days=days))
    db.commit()


def seed_demo_tenant(db: Session, raw_key: str | None) -> Tenant | None:
    """Create the demo tenant for local development. Runs only when ZABAN_DEMO_API_KEY is set."""
    if not raw_key:
        return None
    key_hash = hash_api_key(raw_key)
    tenant = db.query(Tenant).filter(Tenant.api_key_hash == key_hash).first()
    if tenant is None:
        tenant = Tenant(name="Demo Tenant", api_key_hash=key_hash, quota_tokens=5_000_000)
        db.add(tenant)
        db.commit()
    return tenant


def seed_demo_accounts(db: Session, tenant: Tenant | None, settings: Settings) -> None:
    """Create a demo adult and child for trying the website. Runs only when all demo values are set."""
    values = (
        tenant,
        settings.demo_parent_phone,
        settings.demo_student_username,
        settings.demo_student_password,
    )
    if not all(values):
        return
    phone = normalize_phone(settings.demo_parent_phone)
    if phone is None:
        return

    guardian = db.query(Guardian).filter(Guardian.phone == phone).first()
    if guardian is None:
        # Demo only: the demo adult starts with a plan so the lesson flow can be tried right away.
        guardian = Guardian(
            tenant_id=tenant.id,
            phone=phone,
            full_name="Demo Parent",
            password_hash=hash_password(settings.demo_parent_password) if settings.demo_parent_password else None,
            plan_expires_at=utcnow() + timedelta(days=365),
        )
        db.add(guardian)
        db.commit()

    username = settings.demo_student_username.lower()
    if db.query(Student).filter(Student.username == username).first() is None:
        student = Student(
            tenant_id=tenant.id,
            external_user_id="demo-student-1",
            display_name="Demo Student",
            username=username,
            password_hash=hash_password(settings.demo_student_password),
            guardian_id=guardian.id,
            age_band="11-14",
            cefr_level="B1",
        )
        db.add(student)
        db.commit()
        db.add(Consent(student_id=student.id, text_version="v1"))
        db.commit()
