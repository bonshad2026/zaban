# zaban

A one-to-one AI English tutoring service. Each lesson is one student and one AI tutor ("Niko"). The lesson runs by turns: the student speaks or types and presses Send, then Niko answers by voice and text, then the student's turn again.

This project is independent and lives in its own git repository.

## Setup (first time)

1. Copy the example settings file:

   ```bash
   copy .env.example .env
   ```

2. Open `.env` and fill in `SECRET_KEY` and `POSTGRES_PASSWORD` with long random values.
   Generate one with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

`.env` holds every secret and is never committed to git. The code contains no passwords or keys.

## Run with Docker

```bash
docker compose up --build
```

Then open:

- http://localhost:8000 — landing page (Persian / English)
- http://localhost:8000/student — student sign-in
- http://localhost:8000/parent — parent sign-in

To use real Claude replies, set `ANTHROPIC_API_KEY` in `.env`. Without it the app runs in offline mode, which costs nothing.

### Demo accounts (optional, development only)

To create demo accounts for testing, fill these values in `.env` and restart:
`ZABAN_DEMO_API_KEY`, `ZABAN_DEMO_PARENT_PHONE`, `ZABAN_DEMO_STUDENT_USERNAME`, `ZABAN_DEMO_STUDENT_PASSWORD` (the child's PIN).
If any of them is empty, no demo data is created. Never fill these in production.

Without a key the app runs in **offline mode**, so the whole flow can be tested for free. The `mode` field in the API shows `live` or `offline`.

## Accounts

- **Adults** sign in with a mobile number and an SMS code (Kavenegar). An adult can manage children under 18 and can also learn for themself. Their own reports are visible only to them.
- **Children under 18** are not self-registered. A parent creates the child's account with a username and a 4 to 6 digit PIN. After 3 wrong PINs the login pauses for 15 minutes.
- **SMS**: set `KAVENEGAR_API_KEY` and an approved `KAVENEGAR_OTP_TEMPLATE` (one token for the code). Without a key, development uses an in-memory sender and nothing is sent. Production refuses to start without a key.
- An adult can also be created from the command line. Replace the placeholders with real values:

```bash
docker compose exec app python -m zaban.cli parent --phone 09121234567 --name "<full name>"
```

- **Customer sites (tenants)** are created the same way. The API key is shown once:

```bash
docker compose exec app python -m zaban.cli tenant "Customer Name" --quota 1000000 --days 30
```

## Lesson rules

- Parent consent is required before a lesson can start.
- Only one lesson can run per student at a time.
- The server keeps the timer. When time runs out, the lesson closes.
- The student cannot speak while Niko is answering. Send is the only way to submit a turn.
- Links, email addresses, long numbers, and private or technical words are blocked before they reach the model.

## Website sign-in

The website uses HttpOnly cookies, one per sign-in (`zaban_student` for a learner, `zaban_parent` for an adult account). A parent and a child can be signed in on the same computer at the same time. The browser never holds an API key on these pages.

## Public API (for customer sites)

Customer sites call the API from their own server with `X-API-Key`. Routes are under `/v1`:

| Method | Path | Who |
|---|---|---|
| POST | `/students` | tenant key or parent |
| GET | `/students` | tenant key or parent (parents see their own children) |
| GET / PATCH / DELETE | `/students/{id}` | tenant key or parent |
| POST | `/students/{id}/password` | tenant key or parent |
| POST | `/students/{id}/consent` | tenant key or parent |
| POST | `/students/{id}/placement` | tenant key or parent |
| POST | `/students/{id}/plans` | tenant key or parent (consent required) |
| GET | `/students/{id}/usage` | tenant key, parent, or the student |
| POST | `/auth/student-token` | tenant key or parent |
| POST | `/students/{id}/sessions` | tenant key, parent, or the student (consent required) |
| GET | `/students/{id}/sessions/active` | tenant key, parent, or the student |
| GET | `/sessions/{id}` | tenant key, parent, or the student |
| POST | `/sessions/{id}/messages` | tenant key, parent, or the student |
| POST | `/sessions/{id}/end` | tenant key, parent, or the student |
| GET | `/students/{id}/reports/progress` | tenant key, parent, or the student |
| GET | `/students/{id}/reports/parent` | tenant key or parent |
| GET | `/tenant/usage` | tenant key only |

Website sign-in endpoints: `POST /v1/web/user/otp/request` (send a code), `POST /v1/web/user/otp/verify` (sign in, or create the adult account with `full_name`), `POST /v1/web/student/login` (username and PIN), `POST /v1/web/user/self` (learn for yourself), `POST /v1/web/user/logout-all`, `POST /v1/web/logout?role=…`, `GET /v1/web/me?role=…`.

## Run locally without Docker

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn zaban.main:app --reload
```

Local runs use SQLite (`zaban.db`) unless `DATABASE_URL` is set.

## Tests

```bash
pytest
```

## Production

- Set `ENVIRONMENT=production` and a real `SECRET_KEY`. The app refuses to start without it.
- Leave every `ZABAN_DEMO_*` value empty.
- Use HTTPS, so cookies are sent only over secure connections.

## Changing the database schema

The database tables are created on startup, but existing tables are not changed. After a model change, reset the local database:

```bash
docker compose down -v
docker compose up --build
```

This deletes local data. Do not do it on a production database. Use proper migrations there.

## Current limits (MVP)

- **Placement** takes a score from the customer's own test (0 to 100) and maps it to CEFR.
- **Lesson score** and **progress percent** are placeholder formulas (`services/sessions.py`, `services/progress.py`). Replace them with a real model before selling.
- **Topic guard** is rule-based, not a full classifier.
- **Quota** is checked before each call and updated after it, without reserving tokens in advance.
- **Prices** in the config are placeholders.
- **Login limits** are stored in the database: SMS codes allow 1 request per minute, 5 per phone and 20 per IP per hour, and 5 tries per code. PINs lock for 15 minutes after 3 wrong tries. Under several server instances these still work, because the counts are in the database.
- **Not built yet**: a backup code or a way to change a lost mobile number, a sharing option that lets an adult give a parent access to their own reports, and a child-side PIN change.
- **Voice** uses the browser's speech recognition and speech synthesis (Chrome or Edge). Chrome sends the audio to Google. Before real children use it, move speech to a server-side provider with clear data terms. Use headphones so Niko's voice is not picked up by the microphone.
- **Background image** is a built-in SVG under a dark overlay. Replace it with a photo only after confirming its license.
- **PINs and codes**: PINs are hashed with PBKDF2. SMS codes are stored only as HMAC hashes, expire after 5 minutes, and allow 5 tries. A child cannot change their own PIN yet. A parent does it.
- **Adult accounts** are created by the first sign-in with a name. Tenant selection uses the first active tenant, so one tenant per site is assumed.
