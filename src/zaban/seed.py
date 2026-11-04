from sqlalchemy.orm import Session

from zaban.config import Settings
from zaban.models import Consent, Guardian, Student, Tenant
from zaban.security import hash_api_key
from zaban.services.passwords import hash_password


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
    """Create a demo parent and student for trying the website. Runs only when all demo values are set."""
    values = (
        tenant,
        settings.demo_parent_email,
        settings.demo_parent_password,
        settings.demo_student_username,
        settings.demo_student_password,
    )
    if not all(values):
        return

    guardian = db.query(Guardian).filter(Guardian.email == settings.demo_parent_email.lower()).first()
    if guardian is None:
        guardian = Guardian(
            tenant_id=tenant.id,
            email=settings.demo_parent_email.lower(),
            full_name="Demo Parent",
            password_hash=hash_password(settings.demo_parent_password),
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
