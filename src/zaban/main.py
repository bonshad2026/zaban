import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from zaban import models  # noqa: F401  (registers tables before create_all)
from zaban.api import router as api_router
from zaban.billing import router as billing_router
from zaban.config import settings
from zaban.db import Base, SessionLocal, engine
from zaban.reports import router as reports_router
from zaban.seed import seed_demo_accounts, seed_demo_plans, seed_demo_tenant
from zaban.services.sms import dev_outbox
from zaban.web import router as web_router

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.environment == "production" and not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set in production")
    Base.metadata.create_all(engine)
    if settings.environment == "development":
        with SessionLocal() as db:
            tenant = seed_demo_tenant(db, settings.demo_api_key)
            seed_demo_plans(db)
            seed_demo_accounts(db, tenant, settings)
    yield


app = FastAPI(title="zaban", version="0.1.0", lifespan=lifespan)
app.include_router(api_router, prefix="/v1")
app.include_router(reports_router, prefix="/v1")
app.include_router(web_router, prefix="/v1")
app.include_router(billing_router, prefix="/v1")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def landing() -> FileResponse:
    return FileResponse(STATIC_DIR / "landing.html")


@app.get("/student", include_in_schema=False)
def student_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "student.html")


@app.get("/parent", include_in_schema=False)
def parent_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "parent.html")


# Development only: a stand-in bank page and a view of the SMS codes that would have been sent.
@app.get("/dev/pay/{payment_id}", include_in_schema=False)
def dev_pay_page(payment_id: str) -> FileResponse:
    if settings.environment != "development":
        raise HTTPException(status_code=404)
    return FileResponse(STATIC_DIR / "dev-pay.html")


@app.get("/dev/sms-outbox", include_in_schema=False)
def dev_sms_outbox() -> list[dict]:
    if settings.environment != "development":
        raise HTTPException(status_code=404)
    return [{"phone": phone, "code": code} for phone, code in dev_outbox()[-20:]]
