# zaban

An AI-powered English tutoring API. Each session is one-to-one: one student and one AI tutor ("Niko").

This project is independent. It lives in its own git repository and does not depend on any other project.

## Status

Skeleton only. Core features (tenants and API keys, students, session engine, AI gateway, metering, reports) are not built yet.

## Requirements

- Python 3.13+

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Run

```bash
uvicorn zaban.main:app --reload
```

Then open http://127.0.0.1:8000/health.

## Configuration

Copy `.env.example` to `.env` and fill in the values. Never commit `.env`.
