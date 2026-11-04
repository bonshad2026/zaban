import os
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    secret_key: str
    anthropic_api_key: str | None
    model: str
    session_token_ttl_seconds: int
    web_session_ttl_seconds: int
    input_price_per_mtok: float
    output_price_per_mtok: float
    # SMS codes for adult sign-in (Kavenegar). Without a key, codes are kept in memory for development only.
    kavenegar_api_key: str | None
    kavenegar_otp_template: str
    otp_ttl_seconds: int
    # "fake" is for development only. "zarinpal" needs the merchant ID from the company account.
    payment_gateway: str
    zarinpal_merchant_id: str | None
    # Demo values are read from the environment only. Nothing is stored in the code.
    demo_api_key: str | None
    demo_parent_phone: str | None
    demo_student_username: str | None
    demo_student_password: str | None


def load_settings() -> Settings:
    return Settings(
        environment=os.getenv("ENVIRONMENT", "development"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./zaban.db"),
        # Without SECRET_KEY a random one is used for this run only, so sign-ins reset on restart.
        secret_key=os.getenv("SECRET_KEY") or secrets.token_urlsafe(32),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        model=os.getenv("ZABAN_MODEL", "claude-haiku-5-5"),
        session_token_ttl_seconds=int(os.getenv("SESSION_TOKEN_TTL", "900")),
        web_session_ttl_seconds=int(os.getenv("WEB_SESSION_TTL", "43200")),
        # Placeholder prices in USD per million tokens. Set the real values from Anthropic's price list.
        input_price_per_mtok=float(os.getenv("PRICE_INPUT_PER_MTOK", "1.0")),
        output_price_per_mtok=float(os.getenv("PRICE_OUTPUT_PER_MTOK", "5.0")),
        kavenegar_api_key=os.getenv("KAVENEGAR_API_KEY") or None,
        kavenegar_otp_template=os.getenv("KAVENEGAR_OTP_TEMPLATE", "zaban-otp"),
        otp_ttl_seconds=int(os.getenv("OTP_TTL_SECONDS", "300")),
        payment_gateway=os.getenv("PAYMENT_GATEWAY", "fake"),
        zarinpal_merchant_id=os.getenv("ZARINPAL_MERCHANT_ID") or None,
        demo_api_key=os.getenv("ZABAN_DEMO_API_KEY") or None,
        demo_parent_phone=os.getenv("ZABAN_DEMO_PARENT_PHONE") or None,
        demo_student_username=os.getenv("ZABAN_DEMO_STUDENT_USERNAME") or None,
        demo_student_password=os.getenv("ZABAN_DEMO_STUDENT_PASSWORD") or None,
    )


settings = load_settings()
