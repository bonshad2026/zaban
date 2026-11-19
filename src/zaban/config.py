import os
import secrets
from dataclasses import dataclass
from urllib.parse import urlparse


# Only the values that belong to the server are read from the environment. Service keys, prices and contact details are set in the admin panel and stored in the database.
@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    secret_key: str
    session_token_ttl_seconds: int
    web_session_ttl_seconds: int
    # How long an SMS code stays valid, in seconds.
    otp_ttl_seconds: int
    # Demo values are read from the environment only. Nothing is stored in the code.
    demo_api_key: str | None
    demo_parent_phone: str | None
    demo_parent_password: str | None
    # Password for the admin page (/admin). Without it the admin page refuses every sign-in.
    admin_password: str | None
    # The full public address of this site, for example https://example.com/zaban. It is used for every link and the payment return address.
    public_base_url: str
    # The path the site is served under, for example /zaban. Empty when the site is at the root of its domain.
    base_path: str


def load_settings() -> Settings:
    public_base_url = (os.getenv("BASE_URL") or "http://127.0.0.1:8000").rstrip("/")
    return Settings(
        environment=os.getenv("ENVIRONMENT", "development"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./zaban.db"),
        # Without SECRET_KEY a random one is used for this run only, so sign-ins reset on restart.
        secret_key=os.getenv("SECRET_KEY") or secrets.token_urlsafe(32),
        session_token_ttl_seconds=int(os.getenv("SESSION_TOKEN_TTL", "900")),
        web_session_ttl_seconds=int(os.getenv("WEB_SESSION_TTL", "43200")),
        otp_ttl_seconds=int(os.getenv("OTP_TTL_SECONDS", "60")),
        demo_api_key=os.getenv("ZABAN_DEMO_API_KEY") or None,
        demo_parent_phone=os.getenv("ZABAN_DEMO_PARENT_PHONE") or None,
        demo_parent_password=os.getenv("ZABAN_DEMO_PARENT_PASSWORD") or None,
        admin_password=os.getenv("ADMIN_PASSWORD") or None,
        public_base_url=public_base_url,
        base_path=urlparse(public_base_url).path.rstrip("/"),
    )


settings = load_settings()
