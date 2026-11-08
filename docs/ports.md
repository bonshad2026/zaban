# Ports on this computer

Every program uses its own port, so they do not clash. Check a port before you use it:
`netstat -ano | findstr LISTENING | findstr :8020`

| Port | Used by | How to start |
| --- | --- | --- |
| 8020 | zaban in Docker (default) | `docker compose up -d --build` in the zaban folder |
| 8010 | zaban run directly with Python (development and sample data) | see the command below |
| 8000, 8001 | taken by other services on this computer. Do not use them for zaban. | — |
| 5432 | zaban's PostgreSQL inside Docker. It is not published to the computer. | — |

To change the zaban Docker port, set `ZABAN_PORT` in the `.env` file (for example `ZABAN_PORT=8030`) and run `docker compose up -d` again.

Development run with the sample database:

```bash
DATABASE_URL=sqlite:///zaban-sample.db PYTHONPATH=src .venv/Scripts/python.exe -m uvicorn zaban.main:app --port 8010
```

When you add another program, give it a port from the table that is not used yet, and add a row here.
