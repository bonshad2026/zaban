from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from zaban.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Columns added after a table was first created. create_all does not add columns to an existing table.
ADDED_COLUMNS = [
    ("self_tests", "score", "FLOAT"),
    ("usage", "model", "VARCHAR(120)"),
    ("curriculum_topics", "position", "INTEGER NOT NULL DEFAULT 0"),
    ("students", "repeat_topic_id", "VARCHAR(40)"),
    ("guardians", "referral_code", "VARCHAR(8)"),
    ("guardians", "referred_by_id", "VARCHAR(32)"),
    ("guardians", "teacher_id", "VARCHAR(32)"),
    ("lesson_items", "item_id", "INTEGER"),
    ("sessions", "evaluation", "TEXT"),
    ("sessions", "start_prompt", "TEXT"),
    ("billing_plans", "name_en", "VARCHAR(80)"),
    ("consult_requests", "last_name", "VARCHAR(120) NOT NULL DEFAULT ''"),
    ("consult_requests", "subject", "VARCHAR(160) NOT NULL DEFAULT ''"),
    ("consult_requests", "contact_permission", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("guardians", "email", "VARCHAR(190)"),
    ("guardians", "age", "INTEGER"),
    ("guardians", "gender", "VARCHAR(20)"),
    ("guardians", "avatar_data", "TEXT"),
    ("guardians", "plan_started_at", "TIMESTAMP"),
    ("billing_plans", "token_allowance", "INTEGER NOT NULL DEFAULT 1000000"),
    ("guardians", "plan_token_allowance", "INTEGER NOT NULL DEFAULT 0"),
    ("guardians", "plan_tokens_used", "INTEGER NOT NULL DEFAULT 0"),
    ("guardians", "suspended", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("payments", "failure_reason", "VARCHAR(200) NOT NULL DEFAULT ''"),
    ("students", "level_listening", "VARCHAR(4) NOT NULL DEFAULT 'A1'"),
    ("students", "level_reading", "VARCHAR(4) NOT NULL DEFAULT 'A1'"),
    ("students", "level_grammar", "VARCHAR(4) NOT NULL DEFAULT 'A1'"),
    ("students", "level_speaking_writing", "VARCHAR(4) NOT NULL DEFAULT 'A1'"),
    ("students", "level_range", "VARCHAR(4) NOT NULL DEFAULT 'A1'"),
    ("students", "level_accuracy", "VARCHAR(4) NOT NULL DEFAULT 'A1'"),
    ("students", "level_fluency", "VARCHAR(4) NOT NULL DEFAULT 'A1'"),
    ("students", "level_interaction", "VARCHAR(4) NOT NULL DEFAULT 'A1'"),
    ("students", "level_coherence", "VARCHAR(4) NOT NULL DEFAULT 'A1'"),
    ("students", "register_pref", "VARCHAR(12) NOT NULL DEFAULT 'neutral'"),
    ("sessions", "eval_range", "VARCHAR(4)"),
    ("sessions", "eval_accuracy", "VARCHAR(4)"),
    ("sessions", "eval_fluency", "VARCHAR(4)"),
    ("sessions", "eval_interaction", "VARCHAR(4)"),
    ("sessions", "eval_coherence", "VARCHAR(4)"),
    ("sessions", "end_status", "VARCHAR(20) NOT NULL DEFAULT 'active'"),
    ("sessions", "session_kind", "VARCHAR(20) NOT NULL DEFAULT 'lesson'"),
]

# The five speaking criteria start from the speaking level the learner chose before the first lesson.
SPEAKING_CRITERIA = ["level_range", "level_accuracy", "level_fluency", "level_interaction", "level_coherence"]


class Base(DeclarativeBase):
    pass


def allow_lessons_without_text() -> None:
    # A lesson on a topic with no written text has no variant. Databases made before that have the column as NOT NULL.
    if engine.dialect.name != "postgresql" or not inspect(engine).has_table("lesson_topics"):
        return
    column = next(c for c in inspect(engine).get_columns("lesson_topics") if c["name"] == "variant_id")
    if not column["nullable"]:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE lesson_topics ALTER COLUMN variant_id DROP NOT NULL"))


def add_missing_columns() -> None:
    inspector = inspect(engine)
    added: set[tuple[str, str]] = set()
    with engine.begin() as conn:
        for table, column, column_type in ADDED_COLUMNS:
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))
                added.add((table, column))
                if (table, column) == ("guardians", "plan_token_allowance"):
                    # Adults who already paid get a standard allowance, so their plan stays usable until its date.
                    conn.execute(text("UPDATE guardians SET plan_token_allowance = 1000000 WHERE plan_expires_at IS NOT NULL"))
        if ("students", SPEAKING_CRITERIA[0]) in added:
            # Learners who existed before the partner had their speaking level copied into the five criteria, once.
            conn.execute(
                text(
                    "UPDATE students SET level_range = level_speaking_writing, level_accuracy = level_speaking_writing, "
                    "level_fluency = level_speaking_writing, level_interaction = level_speaking_writing, "
                    "level_coherence = level_speaking_writing"
                )
            )
        if ("sessions", "end_status") in added:
            # Sessions that already ended before the status existed: evaluated if they have a summary, otherwise no_evaluation.
            conn.execute(text("UPDATE sessions SET end_status = 'evaluated' WHERE evaluation IS NOT NULL"))
            conn.execute(text("UPDATE sessions SET end_status = 'no_evaluation' WHERE ended_at IS NOT NULL AND evaluation IS NULL"))


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
