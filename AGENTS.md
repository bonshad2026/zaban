# Notes for AI coding agents

This file is for any coding agent (Claude, Codex, or others). It states the project rules that are not obvious from the code. Read `README.md` first, then the note for the area you touch.

## Project

- Python 3.13+ FastAPI app with SQLAlchemy. PostgreSQL in Docker, SQLite for local runs.
- Source is in `src/zaban/`. The public website is static HTML, CSS and JavaScript in `src/zaban/static/`.
- Notes by topic live in `docs/`. The website header and adult account menu are described in `docs/account-menu.md`.
- `docs/site-map.md` is the overview of every page, admin menu group, backend module and main table. Read it before changing the site.

## Commands

- Tests: `pytest` (or `.venv\Scripts\python.exe -m pytest` on Windows). Run a single file with `pytest tests/<file>.py`.
- Docker: `docker compose up -d --build`. The app is at `http://127.0.0.1:8020` on this computer (see `docs/ports.md`).
- Local run on another port: see `docs/ports.md`. Do not use ports 8000 or 8001 for zaban.

## Rules

- **Static files are baked into the image.** After any change under `src/zaban/static/`, rebuild with `docker compose build --no-cache app`, then `docker compose up -d --force-recreate app`. A plain build once served stale files. Check the new text with curl afterwards.
- **Git:** work on a feature branch. Do not commit to `develop` directly. Develop only moves forward with `git merge --ff-only`. Never force-push or reset a shared branch. Do not push unless the user asks.
- **Secrets:** `.env` is never committed. Do not print or copy its values.
- **Child data:** the product serves children. Do not add tools or outputs that expose personal data of children in logs or chat.
- **Persian UI:** public pages are bilingual through `data-fa` and `data-en` attributes and the `ERROR_TEXT` tables in `common.js`. A new server error message needs an entry in both English and Persian tables.
- **Element IDs:** page scripts use short generic IDs such as `infoForm`. Header dialogs use the `acc` prefix so they do not clash with those IDs.

## Where to look

| Topic | Start here |
|---|---|
| Sign-in and accounts | `README.md` (Accounts, Website sign-in), `src/zaban/web.py`, `src/zaban/account.py` |
| Website header and profile menu | `docs/account-menu.md` |
| Curriculum and learning programs | `docs/curriculum.md`, `src/zaban/curriculum_data.py`, `src/zaban/program_data.py` |
| Database columns added after first release | `ADDED_COLUMNS` in `src/zaban/db.py` |
| Port usage on this computer | `docs/ports.md` |
| Pages, admin menu, data and open items | `docs/site-map.md` |
| Prompts (lesson and self-test) | `src/zaban/services/prompt_template.py`, `src/zaban/services/self_test_prompt.py` |
| Help content tags and filters | `src/zaban/services/help_content.py`, `src/zaban/learning_aids.py` |
