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
DEMO_PIN = "1234"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="zaban-demo.db")
    parser.add_argument("--media", required=True, type=Path)
    args = parser.parse_args()

    db_path = (ROOT / args.db).resolve()
    if db_path.exists():
        db_path.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("SECRET_KEY", "demo-only-secret-key-change-me-0123456789")
    os.environ.setdefault("ZABAN_DEMO_API_KEY", "demo-tenant-key-0123456789")
    os.environ.setdefault("ZABAN_DEMO_PARENT_PHONE", "09120000001")
    os.environ.setdefault("ZABAN_DEMO_PARENT_PASSWORD", DEMO_PASSWORD)
    os.environ.setdefault("ZABAN_DEMO_STUDENT_USERNAME", "demo-kid")
    os.environ.setdefault("ZABAN_DEMO_STUDENT_PASSWORD", DEMO_PIN)
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
        LearningProgram,
        LessonItem,
        Message,
        Payment,
        Plan,
        ProgramItem,
        SelfTest,
        SelfTestMessage,
        Student,
        StudentGoal,
        StudentProgress,
        TutorProfile,
        TutorSession,
        utcnow,
    )
    from zaban.seed import seed_demo_accounts, seed_demo_plans, seed_demo_tenant
    from zaban.services.curriculum import seed_curriculum
    from zaban.services.passwords import hash_password
    from zaban.services.programs import ensure_progress, seed_programs
    from zaban.services.self_test import DEFAULT_SELF_TEST_PROMPT, SELF_TEST_PROMPT_KEY

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_curriculum(db)
        seed_programs(db)
        tenant = seed_demo_tenant(db, settings.demo_api_key)
        seed_demo_plans(db)
        seed_demo_accounts(db, tenant, settings)
        db.commit()
        tenant_id = tenant.id if tenant else db.query(Student).first().tenant_id
        now = utcnow()
        plans = db.query(BillingPlan).order_by(BillingPlan.price_toman).all()

        # ----- Adults (parents) with plans, payments and children -----
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

        # ----- Children -----
        def child(guardian: Guardian, username: str, name: str, band: str, level: str, goal: str,
                  details: dict, interests: str, motivation: str) -> Student:
            student = db.query(Student).filter(Student.username == username).first()
            if student is None:
                student = Student(
                    tenant_id=tenant_id, external_user_id=f"demo-{username}", display_name=name,
                    username=username, password_hash=hash_password(DEMO_PIN), guardian_id=guardian.id,
                    age_band=band, cefr_level=level, created_at=now,
                )
                db.add(student)
                db.flush()
            db.merge(LearnerDetails(student_id=student.id, **details))
            db.merge(TutorProfile(student_id=student.id, interests=interests, motivation=motivation,
                                  instructions="Sample notes: be patient and use short sentences."))
            db.merge(StudentGoal(student_id=student.id, goal=goal))
            return student

        sara = child(parisa, "sara-demo", "Sara", "11-14", "A1", "daily_conversation",
                     dict(age=12, gender="female", grade="Grade 6", attributes="kind, likes jokes",
                          conversation_style="story", response_style="playful",
                          level_sample="I like my dog. He is brown.", free_text="I love drawing horses."),
                     "animals, drawing", "talk with friends in English")
        ali = child(parisa, "ali-demo", "Ali", "7-10", "A1", "hobbies",
                    dict(age=8, gender="male", grade="Grade 3", attributes="loves football",
                         conversation_style="quiz", response_style="gentle", level_sample="",
                         free_text="I like football."),
                    "football, cars", "fun hobbies")
        nima = child(reza, "nima-demo", "Nima", "15-18", "B2", "school",
                     dict(age=16, gender="male", grade="Grade 11", attributes="direct, wants feedback",
                          conversation_style="mixed", response_style="direct",
                          level_sample="Yesterday I finished my science project.", free_text=""),
                     "science, music", "pass the English exam")
        db.flush()

        # Sara has a plan: three lessons a week, two months.
        db.add(Plan(
            student_id=sara.id, goal="Daily conversation", months=2, sessions_per_week=3, minutes_per_session=10,
            start_date=now - timedelta(days=14), end_date=now + timedelta(days=46),
            milestones=["Greetings", "Family", "Food", "Daily routine"], status="active",
        ))
        db.flush()

        # Sara's program: she has finished two lessons, so she is on lesson 3.
        progress = ensure_progress(db, sara)
        if progress is not None:
            progress.position = 2
            progress.status = "active"

        # Stage and concepts for the first lessons of the first program (one lesson = one item).
        first = db.query(LearningProgram).order_by(LearningProgram.id).first()
        if first is not None:
            first.duration_months = 24
            stages = {range(0, 6): "Stage 1: greetings", range(6, 12): "Stage 2: family"}
            for item in db.query(ProgramItem).filter(ProgramItem.program_id == first.id).order_by(ProgramItem.position):
                if item.position >= 12:
                    break
                for span, name in stages.items():
                    if item.position in span:
                        item.stage = name
                item.concepts = [f"concept {item.position + 1}a", f"concept {item.position + 1}b"]

        # Two finished lessons with messages and evaluations for Sara.
        def lesson(days_ago: int, minutes: int, score: float, evaluation: str, turns: list[tuple[str, str]]) -> TutorSession:
            started = now - timedelta(days=days_ago)
            session = TutorSession(
                student_id=sara.id, duration_minutes=minutes, status="completed", started_at=started,
                ends_at=started + timedelta(minutes=minutes), ended_at=started + timedelta(minutes=minutes),
                score=score, evaluation=evaluation,
            )
            db.add(session)
            db.flush()
            for role, text in turns:
                db.add(Message(session_id=session.id, role=role, content=text, created_at=started))
            return session

        # The first two lessons are program lessons 1 and 2, so the report shows their titles.
        lesson_one = lesson(9, 10, 72.0,
                            "Sara answered every question in full sentences. Next time, practise the word order in questions.",
                            [("assistant", "Hi Sara! What is your favourite animal?"),
                             ("user", "My favourite animal is horse."),
                             ("assistant", "Nice! Can you say: I like horses because they are fast?"),
                             ("user", "I like horses because they are fast.")])
        lesson_two = lesson(4, 10, 81.0,
                            "Good sentences about family. Try to add one detail to each answer.",
                            [("assistant", "Tell me about your family."),
                             ("user", "I have a brother. He is tall."),
                             ("assistant", "Great! What does your brother like to do?"),
                             ("user", "He likes play football.")])
        # A free talk with no program lesson, so the report shows it as a free conversation.
        lesson(2, 5, 76.0, "Good answers about your weekend. Try longer sentences.",
               [("assistant", "What did you do last weekend?"),
                ("user", "I go to park with my mother.")])
        # The lessons belong to the program Sara is actually in, not to the first program in the table.
        if progress is not None:
            sara_program = db.get(LearningProgram, progress.program_id)
            for position, session in enumerate([lesson_one, lesson_two]):
                db.add(LessonItem(session_id=session.id, program_id=sara_program.id, position=position,
                                  program_version=sara_program.version, counted=True, created_at=session.started_at))

        # ----- Self-tests: one finished, one running -----
        finished = SelfTest(student_id=sara.id, kind="qa", skill="writing", minutes=10, level_used="A1",
                            status="finished", ends_at=now - timedelta(days=1), created_at=now - timedelta(days=1),
                            score=78.0,
                            result="Strengths: clear short answers. Next steps: write three sentences about your day.")
        db.add(finished)
        db.flush()
        for role, text in [("assistant", "Write a sentence about your morning."),
                           ("user", "I wake up at seven. I eat bread."),
                           ("assistant", "Good! Now write one sentence about school.")]:
            db.add(SelfTestMessage(test_id=finished.id, role=role, content=text))

        running = SelfTest(student_id=nima.id, kind="suggested", skill="speaking", minutes=15, level_used="B2",
                           status="active", ends_at=now + timedelta(minutes=15), created_at=now)
        db.add(running)
        db.flush()
        db.add(SelfTestMessage(test_id=running.id, role="assistant",
                               content="Tell me about your science project in two or three sentences."))

        # ----- Consultation and cooperation requests -----
        consults = [
            ("Mina", "Rezaei", "Kids class", "09121230001", "I want a class for my daughter.", "evenings", "new"),
            ("Hossein", "Moradi", "Prices", "09121230002", "How much is the plan?", "afternoons", "reviewed"),
            ("Leila", "Ahmadi", "Teen class", "09121230003", "My son is 15.", "weekends", "called"),
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
            ("Content writing", "09121240003", "writer@example.com", "I can write stories for kids.", "closed"),
        ]:
            db.add(CooperationRequest(subject=subject, phone=phone, email=email, message=message, status=status))

        # ----- Help content: five local sample files, plus one link -----
        media = args.media
        samples = [
            ("Morning podcast: greetings", "podcast", "T", "A1", "school, friends", "sample-podcast-morning.wav", "audio/wav"),
            ("Story: the lost sound", "story", "T", "A1", "animals", "sample-story-sound.wav", "audio/wav"),
            ("Animation cover", "animation", "K", "A1", "animals", "sample-animation-cover.png", "image/png"),
            ("Vocabulary card", "sample", "T", "A2", "food", "sample-vocabulary-card.png", "image/png"),
            ("Story worksheet", "sample", "T", "A1", "stories", "sample-story-worksheet.pdf", "application/pdf"),
        ]
        for title, category, band, level, interests, filename, mime in samples:
            db.add(HelpContent(title=title, category=category, age_band=band, level=level, interests=interests,
                               mime=mime, data=(media / filename).read_bytes(), stage="Stage 1"))
        # Two links so the category tabs have something to show: a video for ages 11 to 14 at A1, and one for teens at B2.
        db.add(HelpContent(title="Sample video: my family", category="video", age_band="T", level="A1",
                           interests="family", url="https://example.com/sample-video"))
        db.add(HelpContent(title="Sample video link", category="video", age_band="S", level="B2",
                           interests="science", url="https://example.com/sample-video"))

        # ----- Admin settings and the self-test prompt -----
        db.merge(AppSetting(key="prompt_mode", value="all"))
        db.merge(AppSetting(key="global_prompt", value="Teach with short, clear sentences. Praise effort before correcting. "
                                                       "Use pictures and stories from everyday life in the UK and US. Never rush the learner."))
        db.merge(AppSetting(key="expected_output",
                            value="Use the words from the last lesson. End each lesson with one short task."))
        db.merge(AppSetting(key=SELF_TEST_PROMPT_KEY, value=DEFAULT_SELF_TEST_PROMPT))
        db.commit()

        counts = {
            "adults": db.query(Guardian).count(),
            "children": db.query(Student).count(),
            "payments": db.query(Payment).count(),
            "consults": db.query(ConsultRequest).count(),
            "cooperations": db.query(CooperationRequest).count(),
            "help_content": db.query(HelpContent).count(),
            "lessons": db.query(TutorSession).count(),
            "self_tests": db.query(SelfTest).count(),
        }
    print(f"demo database ready: {db_path}")
    for key, value in counts.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
