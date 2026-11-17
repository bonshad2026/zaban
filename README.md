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
- http://localhost:8000/login — sign-in (mobile number and password, or an SMS code)

To use real Claude replies, set `ANTHROPIC_API_KEY` in `.env`. Without it the app runs in offline mode, which costs nothing.

### Demo accounts (optional, development only)

To create demo accounts for testing, fill these values in `.env` and restart:
`ZABAN_DEMO_API_KEY`, `ZABAN_DEMO_PARENT_PHONE`, `ZABAN_DEMO_STUDENT_USERNAME`, `ZABAN_DEMO_STUDENT_PASSWORD` (the demo learner's password).
If any of them is empty, no demo data is created. Never fill these in production.

Without a key the app runs in **offline mode**, so the whole flow can be tested for free. The `mode` field in the API shows `live` or `offline`.

## Accounts

- **Adults** are the only website users. They sign in with a mobile number and a password (SMS codes are used to sign up and to reset the password). An adult learns for themself, and only they can see their own reports.
- **Learners created through a customer's API key** sign in with a username and a password. After 3 wrong passwords the login pauses for 15 minutes.
- **SMS**: set `KAVENEGAR_API_KEY` and an approved `KAVENEGAR_OTP_TEMPLATE` (one token for the code). Without a key, development uses an in-memory sender and nothing is sent. Production refuses to start without a key.
- An adult can also be created from the command line. Replace the placeholders with real values:

```bash
docker compose exec app python -m zaban.cli adult --phone 09121234567 --name "<full name>"
```

- **Customer sites (tenants)** are created the same way. The API key is shown once:

```bash
docker compose exec app python -m zaban.cli tenant "Customer Name" --quota 1000000 --days 30
```

## Conversation partner (گفتاریار)

Lessons and free conversation use the conversation partner, described in `docs/conversation-partner.md`.

- The partner answers in JSON. A valid answer is shown and logged; an invalid one is shown as plain text and logs nothing.
- Speech is turned into text in the browser. The server never receives audio, and no outside pronunciation service is used.
- When a lesson's time runs out the learner decides: go on without a time limit, or end it. The end routine (summary, five criteria, notebook) runs at the end or at the next lesson.
- The administrator sets the numbers, rules, level policy, rhythm, the content library and the notebook rule in the «مجموعه پرامپت» group of the admin panel.
- The learner's notebook is never shown to the learner.

## Lesson rules

- Consent is required before a lesson can start. A website adult accepts the terms at sign-up, and that is stored as their consent when their learner profile is created. Customer sites record consent with `POST /students/{id}/consent`.
- Only one lesson can run per student at a time.
- The server keeps the timer. When time runs out, the lesson closes.
- The student cannot speak while Niko is answering. Send is the only way to submit a turn.
- Links, email addresses, long numbers, and private or technical words are blocked before they reach the model.

## Website sign-in

The website uses one HttpOnly cookie, `zaban_student`. Every website user is a student: the adult signs in once and their own learning uses the same cookie. The browser never holds an API key on these pages.

## Public API (for customer sites)

Customer sites call the API from their own server with `X-API-Key`. Routes are under `/v1`:

| Method | Path | Who |
|---|---|---|
| POST | `/students` | tenant key only |
| GET | `/students` | tenant key only |
| GET / PATCH / DELETE | `/students/{id}` | tenant key only (GET also: the student) |
| POST | `/students/{id}/password` | tenant key only |
| POST | `/students/{id}/consent` | tenant key only |
| POST | `/students/{id}/placement` | tenant key only |
| POST | `/students/{id}/plans` | tenant key only (consent required) |
| GET | `/students/{id}/usage` | tenant key or the student |
| POST | `/auth/student-token` | tenant key only |
| POST | `/students/{id}/sessions` | tenant key or the student (consent required) |
| GET | `/students/{id}/sessions/active` | tenant key or the student |
| GET | `/sessions/{id}` | tenant key or the student |
| POST | `/sessions/{id}/messages` | tenant key or the student |
| POST | `/sessions/{id}/end` | tenant key or the student |
| GET | `/students/{id}/reports/progress` | tenant key or the student |
| GET | `/students/{id}/reports/summary` | tenant key only  |
| GET | `/tenant/usage` | tenant key only |

Website sign-in endpoints: `POST /v1/web/user/otp/request` (send a code), `POST /v1/web/user/otp/verify` (sign in, or create the adult account with `full_name`), `POST /v1/web/user/self` (learn for yourself), `POST /v1/web/user/logout-all`, `POST /v1/web/logout`, `GET /v1/web/me`. The adult's profile (name, email, age, gender, photo) is at `GET` and `PUT /v1/web/user/profile`, and the password change is `POST /v1/web/user/password`. The header menu that uses them is described in [docs/account-menu.md](docs/account-menu.md). Agents working in this repo should also read [AGENTS.md](AGENTS.md).

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
- **Login limits** are stored in the database: SMS codes allow 1 request per minute, 5 per phone and 20 per IP per hour, and 5 tries per code. Passwords lock for 15 minutes after 3 wrong tries. Under several server instances these still work, because the counts are in the database.
- **Not built yet**: a backup code or a way to change a lost mobile number, and a sharing option that lets an adult give someone else access to their own reports.
- **Voice** uses the browser's speech recognition and speech synthesis (Chrome or Edge). Chrome sends the audio to Google. Before real users rely on it, move speech to a server-side provider with clear data terms. Use headphones so Niko's voice is not picked up by the microphone.
- **Background image** is a built-in SVG under a dark overlay. Replace it with a photo only after confirming its license.
- **Passwords and codes**: passwords are hashed with PBKDF2. SMS codes are stored only as HMAC hashes, expire after 5 minutes, and allow 5 tries. A learner's password can be changed by the tenant (customer) that created the learner.
- **Adult accounts** are created by the first sign-in with a name. Tenant selection uses the first active tenant, so one tenant per site is assumed.
