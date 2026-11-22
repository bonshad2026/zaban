# Deployment

This is the guide for whoever deploys zaban (Liara or another server). Read it before the first start of a new version.

## 1. What the server needs

Set these as environment variables on the server (Liara: the app's environment settings). Nothing else is read from the environment.

| Variable | Value | Note |
|---|---|---|
| `ENVIRONMENT` | `production` | Required. The app refuses to start without `SECRET_KEY` in production. |
| `SECRET_KEY` | long random text | Required. Keep it: changing it signs everyone out. |
| `DATABASE_URL` | PostgreSQL address | Required in production. |
| `POSTGRES_PASSWORD` | password | Used by the Docker database service. |
| `BASE_URL` | `https://<domain>` or `https://<domain>/zaban` | The full public address. The path is needed when the site shares a domain. This is also the address used for the payment return. |
| `ADMIN_PASSWORD` | strong password | Without it nobody can sign in to `/admin`. |
| `OTP_TTL_SECONDS` | `60` | How long an SMS code is valid. |
| `SESSION_TOKEN_TTL`, `WEB_SESSION_TTL` | `900`, `43200` | Session lengths in seconds. |
| `ZABAN_PORT` | `8020` | Only for Docker Compose. |
| `CONVERSATION_ALLOWED_ORIGINS` | comma-separated URLs | Only if another website calls the conversation API from a browser. |

## 2. Service settings (SMS, payment, AI, prices, contact)

These are **not** environment variables any more. They are kept in the database and set in the admin panel at `/admin` (sections: SMS, Payment, AI model, System settings).

The panel starts empty on a new database, so fill in every section after the first start. Do not put these values in the server's environment: nothing reads them from there.

Values that the panel needs: the SMS key and template, the payment provider and merchant ID, the AI provider, key, and model, the token prices, and the contact phone and email.

## 3. Build and run with Docker

```bash
docker compose build app
docker compose up -d --force-recreate app
docker compose logs --tail 50 app
```

- The packages are a separate cached layer. A normal `docker compose build app` rebuilds only the project, so there is no need for `--no-cache`.
- Static files (HTML, CSS, JavaScript) are part of the image. After any change to them, rebuild the image.
- The app listens on port 8000 inside the container. Docker publishes it on `ZABAN_PORT` (default 8020).

## 4. Check after the deployment

Open the site and check each of these:

- [ ] The home page and the sign-in page open.
- [ ] `/admin` opens and signs in with `ADMIN_PASSWORD`.
- [ ] **SMS:** the SMS section shows the provider as Kavenegar and a key marked as set. Request a sign-in code on a test number.
- [ ] **Payment:** the payment section shows ZarinPal and a merchant ID marked as set. The callback address in the panel uses `BASE_URL`.
- [ ] **AI:** the AI section shows the provider, the model and a key marked as set. A lesson reply comes back (not the offline reply).
- [ ] **Prices and contact:** the token prices are filled, and the contact page shows the details you set.
- [ ] The header on a computer and a phone: sign-in and sign-up for a visitor, and the profile for a signed-in user.

If a panel value is empty, that feature does not work and the user sees a plain message (for example "The SMS could not be sent"). No user is shown anything about settings.

## 5. Before you deploy

- Back up the PostgreSQL database.
- Keep the previous image, so you can go back to it if needed.

To go back: start the previous image again. The database is shared, so any settings changed in the panel stay as they are.

## 6. Local development

For a local run, copy `.env.example` to `.env`, fill in `SECRET_KEY` and `POSTGRES_PASSWORD`, and use `ENVIRONMENT=development`. The development SMS sender and the fake payment gateway are used when the panel is empty.
