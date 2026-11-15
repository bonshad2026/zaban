"""Fill a separate demo database with sample data for every part of the site.

Usage:
    python scripts/seed_demo_data.py --db zaban-demo.db --media <folder with sample files>

The script never touches zaban.db. It creates a new database file, so the data can be deleted by removing that file.
Sample files for the help content library are read from --media. Nothing is downloaded.
"""

import argparse
import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DEMO_PASSWORD = "Demo-pass-123"
DEMO_LEARNER_PASSWORD = "1234"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="zaban-demo.db")
    parser.add_argument("--database-url", default=None,
                        help="Use this database instead of a new file, for example the PostgreSQL in Docker.")
    parser.add_argument("--media", required=True, type=Path)
    args = parser.parse_args()

    if args.database_url:
        # The data goes into the given database. Nothing is deleted first; run it on a database that has no sample data yet.
        db_path = args.database_url
        os.environ["DATABASE_URL"] = args.database_url
    else:
        db_path = (ROOT / args.db).resolve()
        if db_path.exists():
            db_path.unlink()
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("SECRET_KEY", "demo-only-secret-key-change-me-0123456789")
    os.environ.setdefault("ZABAN_DEMO_API_KEY", "demo-tenant-key-0123456789")
    os.environ.setdefault("ZABAN_DEMO_PARENT_PHONE", "09120000001")
    os.environ.setdefault("ZABAN_DEMO_PARENT_PASSWORD", DEMO_PASSWORD)
    os.environ.setdefault("ZABAN_DEMO_STUDENT_USERNAME", "demo-learner")
    os.environ.setdefault("ZABAN_DEMO_STUDENT_PASSWORD", DEMO_LEARNER_PASSWORD)
    os.environ.setdefault("ADMIN_PASSWORD", "admin-demo-123")
    os.environ.pop("ANTHROPIC_API_KEY", None)  # Seeding never calls the model, so no cost is made.

    from zaban import models  # noqa: F401  (registers every table)
    from zaban.config import settings
    from zaban.db import Base, SessionLocal, engine
    from zaban.models import (
        AppSetting,
        BillingPlan,
        ConsultRequest,
        CooperationRequest,
        Guardian,
        HelpContent,
        LearnerDetails,
        Message,
        Payment,
        Plan,
        SelfTest,
        SelfTestMessage,
        Student,
        StudentGoal,
        TutorProfile,
        TutorSession,
        utcnow,
    )
    from zaban.seed import seed_demo_accounts, seed_demo_plans, seed_demo_tenant
    from zaban.services.curriculum import seed_curriculum
    from zaban.services.passwords import hash_password
    
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_curriculum(db)
        tenant = seed_demo_tenant(db, settings.demo_api_key)
        seed_demo_plans(db)
        seed_demo_accounts(db, tenant, settings)
        db.commit()
        tenant_id = tenant.id if tenant else db.query(Student).first().tenant_id
        now = utcnow()
        plans = db.query(BillingPlan).order_by(BillingPlan.price_toman).all()

        # ----- Adults with plans and payments -----
        def adult(phone: str, name: str, days_left: int) -> Guardian:
            guardian = db.query(Guardian).filter(Guardian.phone == phone).first()
            if guardian is None:
                guardian = Guardian(tenant_id=tenant_id, phone=phone, full_name=name,
                                    password_hash=hash_password(DEMO_PASSWORD), created_at=now)
                db.add(guardian)
                db.flush()
            guardian.plan_expires_at = now + timedelta(days=days_left)
            return guardian

        parisa = adult("09121110001", "Parisa Karimi", 25)
        reza = adult("09121110002", "Reza Ahmadi", 0)
        db.flush()

        def payment(guardian: Guardian, plan: BillingPlan, status: str, days_ago: int) -> None:
            when = now - timedelta(days=days_ago)
            db.add(Payment(
                guardian_id=guardian.id, plan_id=plan.id, amount_toman=plan.price_toman, status=status,
                gateway="fake", gateway_ref=f"demo-{status}-{days_ago}", created_at=when,
                confirmed_at=when if status == "confirmed" else None,
            ))

        payment(parisa, plans[0], "confirmed", 30)
        payment(parisa, plans[-1], "paid", 2)
        payment(parisa, plans[0], "pending", 0)
        payment(reza, plans[0], "failed", 5)

        # ----- Consultation and cooperation requests -----
        consults = [
                        ("Hossein", "Moradi", "Prices", "09121230002", "How much is the plan?", "afternoons", "reviewed"),
                        ("Amir", "Sadeghi", "Adult class", "09121230004", "Call me again next week.", "", "recall"),
            ("Parvin", "Tavakoli", "Technical question", "09121230005", "Waiting for the parent's answer.", "", "awaiting_reply"),
        ]
        for name, last, subject, phone, message, when, status in consults:
            db.add(ConsultRequest(name=name, last_name=last, subject=subject, phone=phone, message=message,
                                  preferred_time=when or None, contact_permission=True, status=status,
                                  created_at=now - timedelta(days=len(name))))
        for subject, phone, email, message, status in [
            ("Teaching partner", "09121240001", "teacher@example.com", "I teach English in Tehran.", "new"),
            ("School partnership", "09121240002", None, "We want to offer Zaban to our students.", "contacted"),
            ("Content writing", "09121240003", "writer@example.com", "I can write stories for adults.", "closed"),
        ]:
            db.add(CooperationRequest(subject=subject, phone=phone, email=email, message=message, status=status))

        # ----- Help content: five local sample files, plus one link -----
        media = args.media
        samples = [
            ("Morning podcast: greetings", "podcast", "A", "A1", "school, friends", "podcast-sample.wav", "audio/wav"),
            ("Story: the lost sound", "story", "A", "A1", "animals", "story-sample.pdf", "application/pdf"),
            ("Animation cover", "animation", "A", "A1", "animals", "animation-sample.png", "image/png"),
            ("Vocabulary card", "sample", "A", "A2", "food", "guide-sample.pdf", "application/pdf"),
            ("Story worksheet", "sample", "A", "A1", "stories", "sample-worksheet.pdf", "application/pdf"),
        ]
        for title, category, band, level, interests, filename, mime in samples:
            db.add(HelpContent(title=title, category=category, age_band=band, level=level, interests=interests,
                               mime=mime, data=(media / filename).read_bytes(), stage="Stage 1"))
        # Links for the other categories, at A1.
        db.add(HelpContent(title="Podcast: my day in English", category="podcast", age_band="A", level="A1",
                           interests="daily routine", url="https://example.com/podcast-my-day"))
        db.add(HelpContent(title="Story: Milo at school", category="story", age_band="A", level="A1",
                           interests="school, animals", url="https://example.com/story-milo"))
        db.add(HelpContent(title="Animation: colours", category="animation", age_band="A", level="A1",
                           interests="colours", url="https://example.com/animation-colours"))
        # Two links so the category tabs have something to show.
        db.add(HelpContent(title="Sample video: my family", category="video", age_band="A", level="A1",
                           interests="family", url="https://example.com/sample-video"))
        db.add(HelpContent(title="Sample video link", category="video", age_band="A", level="B2",
                           interests="science", url="https://example.com/sample-video"))

        # ----- Admin settings and the self-test prompt -----
        db.merge(AppSetting(key="prompt_mode", value="all"))
        db.merge(AppSetting(key="global_prompt", value="Teach with short, clear sentences. Praise effort before correcting. "
                                                       "Use pictures and stories from everyday life in the UK and US. Never rush the learner."))
        db.merge(AppSetting(key="expected_output",
                            value="Use the words from the last lesson. End each lesson with one short task."))
        db.commit()

        counts = {
            "adults": db.query(Guardian).count(),
            "payments": db.query(Payment).count(),
            "consults": db.query(ConsultRequest).count(),
            "cooperations": db.query(CooperationRequest).count(),
            "help_content": db.query(HelpContent).count(),
            "self_tests": db.query(SelfTest).count(),
        }
    print(f"demo database ready: {'the database from --database-url' if args.database_url else db_path}")
    for key, value in counts.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
