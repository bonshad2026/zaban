from sqlalchemy.orm import Session

from datetime import timedelta

from zaban.config import Settings
from zaban.models import BillingPlan, Guardian, Tenant, utcnow
from zaban.security import hash_api_key
from zaban.services.otp import normalize_phone
from zaban.services.passwords import hash_password

# Development prices. The real prices are set by the company, not in code.
DEMO_PLAN_NAMES_EN = {"مقدماتی (نمونه)": "Basic (sample)", "پیشرفته (نمونه)": "Advanced (sample)"}
DEMO_PLANS = [
    ("مقدماتی (نمونه)", "نمونه برای آزمایش", 1_000_000, 30, 500_000),
    ("پیشرفته (نمونه)", "نمونه برای آزمایش", 2_000_000, 90, 1_500_000),
]


# The one plan the service sells for now. Monthly, with a fixed price and a token allowance.
DEFAULT_PLAN_NAME = "پلن ماهانه"
DEFAULT_PLAN_PRICE_TOMAN = 1_000_000
DEFAULT_PLAN_DAYS = 30
DEFAULT_PLAN_TOKENS = 1_000_000


def ensure_default_plan(db: Session) -> None:
    """Create the monthly plan once. While it is the only plan, every other plan is switched off."""
    plan = db.query(BillingPlan).filter(BillingPlan.name == DEFAULT_PLAN_NAME).first()
    if plan is None:
        plan = BillingPlan(
            name=DEFAULT_PLAN_NAME,
            name_en="Monthly plan",
            description="اعتبار یک ماهه با سقف توکن مشخص",
            price_toman=DEFAULT_PLAN_PRICE_TOMAN,
            days=DEFAULT_PLAN_DAYS,
            token_allowance=DEFAULT_PLAN_TOKENS,
        )
        db.add(plan)
        db.flush()
        db.query(BillingPlan).filter(BillingPlan.id != plan.id).update({"active": False})
        db.commit()


def seed_demo_plans(db: Session) -> None:
    """Create sample plans for local development. Does nothing when plans already exist."""
    if db.query(BillingPlan).first() is not None:
        return
    for name, description, price, days, tokens in DEMO_PLANS:
        db.add(BillingPlan(name=name, name_en=DEMO_PLAN_NAMES_EN.get(name), description=description, price_toman=price, days=days, token_allowance=tokens))
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
    """Create a demo adult for trying the website. Runs only when the demo values are set.

    The adult learns for themself from the learner page, so no child account is created.
    """
    if not (tenant and settings.demo_parent_phone):
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
            plan_token_allowance=10_000_000,
        )
        db.add(guardian)
        db.commit()
