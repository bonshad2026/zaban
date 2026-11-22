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

- **Static files are baked into the image.** After any change under `src/zaban/static/`, rebuild with `docker compose build app` (not `--no-cache`: the Dockerfile keeps the packages in their own cached layer, so only the project is rebuilt), then `docker compose up -d --force-recreate app`. Check the new text with curl afterwards.
- **Front end: Bootstrap first.** The pages use Bootstrap 5.3.3 from jsDelivr (`#bsCss` in each page's head). `common.js` swaps the RTL build for the LTR build when the language changes. Use Bootstrap's own classes (`d-flex`, `gap-*`, `btn`, `nav-link`, `dropdown-*`, `order-*`) wherever they exist. Keep custom classes to a minimum. `css/app.css` holds only the site palette (Bootstrap variables are mapped to the theme's `--bg`, `--card`, `--text`, `--accent`, `--border`) and the few things Bootstrap does not cover.
- **Header and menus.** The header is `partials/header.html`. The order of its items is set by `order-*` rules in `css/app.css`: Persian (sidebar on the right) and English (sidebar on the left) are mirrors. On a phone the menu is one ☰ button beside the profile. The profile menu and the language list open from the side of their button (`data-side`, set in `common.js`), and close on a tap outside. Do not add a second header markup.
- **Member pages.** Every learner section starts with an accent title inside its first card, the same text as its menu item. A new learner section follows that pattern.
- **Drop-down lists.** Every `<select>` is drawn with a Bootstrap menu by `common.js`. The native `select` stays in the page and holds the value, so scripts keep reading and setting `select.value`.
- **Service settings live in the admin panel.** Keys for SMS, payment, AI, token prices and the contact details are stored in the database (`AppSetting`) and set in `/admin`. Nothing reads them from the environment. The environment keeps only the server values: `SECRET_KEY`, `POSTGRES_PASSWORD`, `ENVIRONMENT`, `BASE_URL`, `ADMIN_PASSWORD`, the session lengths, `OTP_TTL_SECONDS`, `ZABAN_PORT` and `CONVERSATION_ALLOWED_ORIGINS`. Missing panel values fall back to the defaults in `services/settings_store.py`. The site address comes from `BASE_URL` only.
- **Navigation:** member pages (`/student`, `/plan`, `/learning-info`, `/level`, `/students`, `/payments`, `/requests`, `/referrals`) open inside the shell page `/app`, which keeps the header and the side menu in place. In JavaScript, navigate with `Z.go(path)` (or `Z.go(path, true)` to replace), never with `location.href` or `location.replace`, so a page inside the frame moves the whole window. Member lists live in `MEMBER_PATHS` in `common.js`; add a new member page to that list.
- **Base path:** the site can run under `BASE_URL` (for example `https://example.com/zaban`). On the server, write links with `with_base()` from `zaban/base.py`, and set cookies with `cookie_path()`. In JavaScript, write addresses with `Z.url()`. Never write a root-relative address (`href="/..."`) that the browser will follow without the base path.
- **Cache version:** the pages load `app.css`, `common.js` and the other scripts with `?v=N`. After a change to any of them, bump N in the pages that load them, or browsers keep the old file.
- **Git:** work on a feature branch. Do not commit to `develop` directly. Develop only moves forward with `git merge --ff-only`. Never force-push or reset a shared branch. Do not push unless the user asks.
- **Secrets:** `.env` is never committed. Do not print or copy its values.
- **Adults only:** the product serves adults only. Every learner is an adult who learns for themself (`self_owner_id`), or a learner created through a customer's API key. Do not add child (under 18) account types, age bands other than `adult`, parent-managed learners, or school-grade fields. On 2026-11-15 the owner removed all child logic (code, curriculum rows for bands K, J, T, S, the `purge-children` command, child demo data), and the test data with under-18 records was deleted. If a request seems to need child support, ask the owner first. Report counts only, never names.
- **Persian UI:** public pages are bilingual through `data-fa` and `data-en` attributes and the `ERROR_TEXT` tables in `common.js`. A new server error message needs an entry in both English and Persian tables.
- **Element IDs:** page scripts use short generic IDs such as `infoForm`. Header dialogs use the `acc` prefix so they do not clash with those IDs.

## Where to look

| Topic | Start here |
|---|---|
| Sign-in and accounts | `README.md` (Accounts, Website sign-in), `src/zaban/web.py`, `src/zaban/account.py`, sign-in page `static/login.html` (`/login`) |
| Website header, profile menu and the shell (`/app`) | `docs/account-menu.md` |
| Curriculum and learning programs | `docs/curriculum.md`, `src/zaban/curriculum_data.py`, `src/zaban/program_data.py` |
| Conversation partner (modes, learner profile, level policy, output contract, teacher notebook, build plan) | `docs/conversation-partner.md` v0.7 (design v0.7, built in phases 0 to 7; status per phase in section 15, open checks in section 15.11), sample prompts in `docs/prompt-example.html`. Test plan for a tester: `docs/po-test-plan.md` |
| Database columns added after first release | `ADDED_COLUMNS` in `src/zaban/db.py` |
| Service settings (SMS, payment, AI, prices, contact) | `src/zaban/services/settings_store.py`, admin panel `static/admin.html` and `static/js/admin.js`, endpoints in `src/zaban/admin_ops.py` |
| Deployment and server variables | `docs/deployment.md` |
| Header, profile menu, language and theme | `static/partials/header.html`, `static/css/app.css` (end of file), `static/js/common.js` (`initSiteHeader`, `initLang`, `initTheme`) |
| Port usage on this computer | `docs/ports.md` |
| Pages, admin menu, data and open items | `docs/site-map.md` |
| Prompts (lesson and self-test) | `src/zaban/services/prompt_template.py`, `src/zaban/services/self_test_prompt.py` |
| Help content tags and filters | `src/zaban/services/help_content.py`, `src/zaban/learning_aids.py` |
