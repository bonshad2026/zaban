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
    ("lesson_items", "item_id", "INTEGER"),
    ("student_progress", "revisit_item_id", "INTEGER"),
    ("sessions", "evaluation", "TEXT"),
    ("sessions", "start_prompt", "TEXT"),
    ("program_items", "title_en", "VARCHAR(160)"),
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
]


class Base(DeclarativeBase):
    pass


def add_missing_columns() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, column, column_type in ADDED_COLUMNS:
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))
                if (table, column) == ("guardians", "plan_token_allowance"):
                    # Adults who already paid get a standard allowance, so their plan stays usable until its date.
                    conn.execute(text("UPDATE guardians SET plan_token_allowance = 1000000 WHERE plan_expires_at IS NOT NULL"))


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
