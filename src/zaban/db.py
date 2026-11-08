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
    ("sessions", "evaluation", "TEXT"),
    ("sessions", "start_prompt", "TEXT"),
    ("consult_requests", "last_name", "VARCHAR(120) NOT NULL DEFAULT ''"),
    ("consult_requests", "subject", "VARCHAR(160) NOT NULL DEFAULT ''"),
    ("consult_requests", "contact_permission", "BOOLEAN NOT NULL DEFAULT FALSE"),
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


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
