"""Build output for the site: code, database data, media files, and the database schema changes.

Usage (or run the thin wrapper scripts/build_export.py):
    python scripts/build_export.py --out <folder> [--since <git ref>] [--no-data] [--target-db <url>]

- code/: the site code. With --since, only the files changed since that git ref (added, changed or new).
- database/data.json: all rows, as JSON. Skipped with --no-data.
- media/: stored files (help content and voice samples), with media/index.json. Skipped with --no-data.
- schema/schema_changes.sql: the table and column changes the target database needs, kept apart from the data,
  so a release never has to move existing data again.
"""

import argparse
import base64
import json
import shutil
import subprocess
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.schema import CreateTable

# The repository root: src/zaban/services/export.py is three folders below it.
ROOT = Path(__file__).resolve().parents[3]

from zaban import models  # noqa: E402,F401  (registers every table on Base.metadata)
from zaban.config import settings  # noqa: E402
from zaban.db import Base  # noqa: E402

CODE_PATHS = ["src", "tests", "docs", "scripts", "pyproject.toml", "README.md", "Dockerfile", "docker-compose.yml"]
MEDIA_EXT = {"audio/mpeg": "mp3", "audio/wav": "wav", "audio/ogg": "ogg", "audio/mp4": "m4a", "video/mp4": "mp4",
             "application/pdf": "pdf", "image/png": "png"}


# Never exported: transient sign-in codes, and the stored hashes of passwords and API keys.
SKIPPED_TABLES = {"otp_codes"}
SENSITIVE_COLUMNS = {"students": {"password_hash"}, "guardians": {"password_hash"}, "tenants": {"api_key_hash"}}


def _git(*args: str) -> list[str]:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
    return [line for line in result.stdout.splitlines() if line.strip()]


def code_files(since: str | None) -> list[str]:
    try:
        if since:
            changed = _git("diff", "--name-only", "--diff-filter=ACMR", since, "--", *CODE_PATHS)
            untracked = _git("ls-files", "--others", "--exclude-standard", "--", *CODE_PATHS)
            files = set(changed) | set(untracked)
        else:
            files = set(_git("ls-files", "--", *CODE_PATHS))
    except (OSError, subprocess.CalledProcessError):
        # Not a git checkout (for example an installed copy): export every file under the code folders.
        if since:
            raise ValueError("--since needs a git checkout")
        files = set()
        for path in CODE_PATHS:
            target = ROOT / path
            if target.is_file():
                files.add(path)
            elif target.is_dir():
                files.update(str(p.relative_to(ROOT)) for p in target.rglob("*") if p.is_file())
    return sorted(f for f in files if (ROOT / f).is_file() and "__pycache__" not in f)


def export_code(out: Path, since: str | None) -> list[str]:
    copied = []
    for rel in code_files(since):
        target = out / "code" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
        copied.append(rel)
    return copied


def _jsonable(value):
    if isinstance(value, bytes):
        return {"__bytes_base64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def export_data(out: Path, engine) -> dict[str, int]:
    counts = {}
    dump = {}
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name in SKIPPED_TABLES or not inspect(conn).has_table(table.name):
                continue
            hidden = SENSITIVE_COLUMNS.get(table.name, set())
            rows = [{k: v for k, v in dict(row._mapping).items() if k not in hidden} for row in conn.execute(table.select())]
            dump[table.name] = [{k: _jsonable(v) for k, v in row.items()} for row in rows]
            counts[table.name] = len(rows)
    (out / "database").mkdir(parents=True, exist_ok=True)
    (out / "database" / "data.json").write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    return counts


def export_media(out: Path, engine) -> list[dict]:
    index = []
    media_dir = out / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    with engine.connect() as conn:
        inspector = inspect(conn)
        for table_name, title_col in (("help_content", "title"), ("voice_samples", "name")):
            if not inspector.has_table(table_name):
                continue
            for row in conn.execute(Base.metadata.tables[table_name].select()):
                data = row._mapping.get("data")
                if not data:
                    continue
                mime = row._mapping["mime"]
                name = f"{table_name}-{row._mapping['id']}.{MEDIA_EXT.get(mime, 'bin')}"
                (media_dir / name).write_bytes(data)
                index.append({"file": name, "table": table_name, "id": row._mapping["id"],
                              "title": row._mapping[title_col], "mime": mime})
    (media_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def _default_sql(column) -> str | None:
    # The Python-side default of a column, written as SQL, so existing rows get a real value.
    default = column.default
    if default is None or not getattr(default, "is_scalar", False):
        return None
    value = default.arg
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return None


def _add_column_sql(table: str, column, dialect) -> str:
    col_type = column.type.compile(dialect=dialect)
    default_sql = _default_sql(column)
    if column.nullable or default_sql is None:
        # Without a default, existing rows cannot get a value, so the column is added as nullable and flagged.
        note = "" if column.nullable else f"-- REVIEW: {table}.{column.name} is NOT NULL with no default; set values for existing rows\n"
        return f"{note}ALTER TABLE {table} ADD COLUMN {column.name} {col_type};"
    return f"ALTER TABLE {table} ADD COLUMN {column.name} {col_type} NOT NULL DEFAULT {default_sql};"


def schema_changes(target_url: str) -> list[str]:
    # Compares the models with the target database. Missing tables are created in full; missing columns are added.
    # A new NOT NULL column without a default is flagged for review, because existing rows need a value.
    engine = create_engine(target_url)
    dialect = engine.dialect
    statements = []
    with engine.connect() as conn:
        inspector = inspect(conn)
        existing = set(inspector.get_table_names())
        for table in Base.metadata.sorted_tables:
            if table.name not in existing:
                statements.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
                continue
            current = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in current:
                    continue
                statements.append(_add_column_sql(table.name, column, dialect))
    engine.dispose()
    return statements


def build(out: Path, since: str | None, with_data: bool, target_url: str) -> dict:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    summary = {"code_files": len(export_code(out, since)), "since": since}
    statements = schema_changes(target_url)
    (out / "schema").mkdir(parents=True, exist_ok=True)
    header = f"-- zaban schema changes, generated {date.today().isoformat()}\n"
    (out / "schema" / "schema_changes.sql").write_text(header + "\n".join(statements) + "\n", encoding="utf-8")
    summary["schema_statements"] = len(statements)
    if with_data:
        engine = create_engine(settings.database_url)
        summary["rows"] = export_data(out, engine)
        summary["media_files"] = len(export_media(out, engine))
        engine.dispose()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--since", help="git ref; only code changed since this ref is exported")
    parser.add_argument("--no-data", action="store_true", help="skip database rows and media files")
    parser.add_argument("--target-db", default=settings.database_url, help="database the schema is compared with")
    args = parser.parse_args()
    print(json.dumps(build(args.out, args.since, not args.no_data, args.target_db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
