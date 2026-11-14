import os
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from zaban import models  # noqa: F401  (registers tables before create_all)
from zaban.api import router as api_router
from zaban.admin import router as admin_router
from zaban.billing import router as billing_router
from zaban.config import settings
from zaban.conversation import models as conversation_models  # noqa: F401  (registers the conversation tables)
from zaban.conversation.api import router as conversation_router
from zaban.db import Base, SessionLocal, add_missing_columns, engine
from zaban.reports import router as reports_router
from zaban.seed import ensure_default_plan, seed_demo_accounts, seed_demo_plans, seed_demo_tenant
from zaban.placement_web import router as placement_router
from zaban.services.placement_test import ensure_bank as ensure_placement_bank
from zaban.public import router as public_router
from zaban.services.curriculum import ensure_topic_positions, seed_curriculum
from zaban.services.referrals import ensure_referral_codes
from zaban.services.help_content import seed_help_facets, seed_help_samples
from zaban.services.sms import dev_outbox
from zaban.admin_ops import router as admin_ops_router
from zaban.ai_api import router as ai_router
from zaban.learning_aids import parent_router as learning_parent_router
from zaban.learning_aids import router as learning_aids_router
from zaban.account import router as account_router
from zaban.web import router as web_router

STATIC_DIR = Path(__file__).parent / "static"
PARTIALS_DIR = STATIC_DIR / "partials"


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.environment == "production" and not os.getenv("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set in production")
    Base.metadata.create_all(engine)
    add_missing_columns()
    with SessionLocal() as db:
        seed_curriculum(db)
        ensure_topic_positions(db)
        ensure_referral_codes(db)
        seed_help_facets(db)
        seed_help_samples(db)
    if settings.environment == "development":
        with SessionLocal() as db:
            tenant = seed_demo_tenant(db, settings.demo_api_key)
            seed_demo_plans(db)
            ensure_default_plan(db)
            ensure_placement_bank(db)
            seed_demo_accounts(db, tenant, settings)
    yield


# The interactive API page and the API description are shown only in development. Production does not publish them.
_docs_url = "/docs" if settings.environment == "development" else None
app = FastAPI(
    title="zaban",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=None,
    openapi_url="/openapi.json" if _docs_url else None,
)
# Other websites (for example the learner app on its own server) may call the conversation routes from the browser.
# Only the sites listed in CONVERSATION_ALLOWED_ORIGINS are allowed; the list is comma separated.
_conversation_origins = [origin.strip() for origin in os.getenv("CONVERSATION_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
if _conversation_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_conversation_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
app.include_router(api_router, prefix="/v1")
app.include_router(conversation_router, prefix="/v1")
app.include_router(reports_router, prefix="/v1")
app.include_router(web_router, prefix="/v1")
app.include_router(account_router, prefix="/v1")
app.include_router(learning_aids_router, prefix="/v1")
app.include_router(learning_parent_router, prefix="/v1")
app.include_router(ai_router, prefix="/v1")
app.include_router(billing_router, prefix="/v1")
app.include_router(placement_router, prefix="/v1")
app.include_router(public_router, prefix="/v1")
app.include_router(admin_router, prefix="/v1")
app.include_router(admin_ops_router, prefix="/v1")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _contact_block() -> str:
    # Only the details that are set in .env are shown, so an empty value never leaves a blank row.
    rows = []
    if settings.contact_phone:
        phone = escape(settings.contact_phone)
        rows.append(f'<p class="contact-row"><span data-fa="شماره‌ی تماس" data-en="Phone">شماره‌ی تماس</span><a href="tel:{phone}">{phone}</a></p>')
    if settings.contact_email:
        email = escape(settings.contact_email)
        rows.append(f'<p class="contact-row"><span data-fa="ایمیل" data-en="Email">ایمیل</span><a href="mailto:{email}">{email}</a></p>')
    return f'<div class="contact-details reveal">{"".join(rows)}</div>' if rows else ""


def _page(name: str, current: str = "") -> HTMLResponse:
    # Every page gets the same header, so moving between pages keeps the same frame.
    # The link to the current page is marked, so the menu shows where the visitor is.
    header = (PARTIALS_DIR / "header.html").read_text(encoding="utf-8")
    if current:
        header = header.replace(f'href="{current}"', f'href="{current}" aria-current="page"')
    html = (STATIC_DIR / name).read_text(encoding="utf-8")
    html = html.replace("<!--contact-details-->", _contact_block())
    # The copyright footer goes at the end of every page.
    footer = (PARTIALS_DIR / "footer.html").read_text(encoding="utf-8")
    # The page content sits in one block that grows to fill the screen, so the footer stays at the bottom even on short pages.
    # The side menu sits beside the content. It is empty and hidden until someone signs in.
    html = html.replace("</body>", f"</div></div>{footer}</body>")
    layout = '<div class="app-layout"><nav class="app-side" id="memberNav" aria-label="بخش من" hidden></nav><div class="site-main">'
    return HTMLResponse(html.replace("<!--site-header-->", f"{header}{layout}"))


@app.get("/", include_in_schema=False)
def landing() -> HTMLResponse:
    return _page("landing.html", "/")


@app.get("/student", include_in_schema=False)
def student_page() -> HTMLResponse:
    return _page("student.html", "/student")


@app.get("/parent", include_in_schema=False)
def parent_page() -> HTMLResponse:
    return _page("parent.html", "/parent")


@app.get("/signup", include_in_schema=False)
def signup_page() -> HTMLResponse:
    return _page("signup.html", "/signup")


@app.get("/profile", include_in_schema=False)
def profile_page() -> HTMLResponse:
    return _page("profile.html", "/profile")


@app.get("/requests", include_in_schema=False)
def requests_page() -> HTMLResponse:
    return _page("requests.html", "/requests")


@app.get("/referrals", include_in_schema=False)
def referrals_page() -> HTMLResponse:
    return _page("referrals.html", "/referrals")


@app.get("/plan", include_in_schema=False)
def plan_page() -> HTMLResponse:
    return _page("plan.html", "/plan")


@app.get("/level", include_in_schema=False)
def level_page() -> HTMLResponse:
    return _page("level.html", "/level")


@app.get("/payments", include_in_schema=False)
def payments_page() -> HTMLResponse:
    return _page("payments.html", "/payments")


@app.get("/demo", include_in_schema=False)
def demo_page() -> HTMLResponse:
    return _page("demo.html", "/demo")


@app.get("/consult", include_in_schema=False)
def consult_page() -> HTMLResponse:
    return _page("consult.html", "/consult")


@app.get("/cooperation", include_in_schema=False)
def cooperation_page() -> HTMLResponse:
    return _page("cooperation.html", "/cooperation")


@app.get("/about", include_in_schema=False)
def about_page() -> HTMLResponse:
    return _page("about.html", "/about")


@app.get("/contact", include_in_schema=False)
def contact_page() -> HTMLResponse:
    return _page("contact.html", "/contact")


@app.get("/admin", include_in_schema=False)
def admin_page() -> HTMLResponse:
    return _page("admin.html", "/admin")


# Development only: a stand-in bank page and a view of the SMS codes that would have been sent.
@app.get("/dev/pay/{payment_id}", include_in_schema=False)
def dev_pay_page(payment_id: str) -> HTMLResponse:
    if settings.environment != "development":
        raise HTTPException(status_code=404)
    return _page("dev-pay.html")


@app.get("/dev/sms-outbox", include_in_schema=False)
def dev_sms_outbox() -> list[dict]:
    if settings.environment != "development":
        raise HTTPException(status_code=404)
    return [{"phone": phone, "code": code} for phone, code in dev_outbox()[-20:]]
