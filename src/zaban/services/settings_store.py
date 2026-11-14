from sqlalchemy.orm import Session as DBSession

from zaban.models import AppSetting, utcnow

# Settings the administrator changes in the panel. The two secrets below are stored in the database and are only ever shown masked.
# An empty value falls back to the environment variable.
PROMPT_MODE_KEY = "prompt_mode"
EXPECTED_OUTPUT_KEY = "expected_output"
PAYMENT_PROVIDER_KEY = "payment_provider"  # fake, zarinpal
SMS_PROVIDER_KEY = "sms_provider"  # kavenegar, dev
SMS_TEMPLATE_KEY = "sms_otp_template"
SMS_API_KEY_KEY = "sms_api_key"  # secret: shown masked only
ZARINPAL_MERCHANT_KEY = "zarinpal_merchant_id"  # secret: shown masked only
# The address the site is reached at from outside, for example https://zaban.example.com. The payment gateway returns the buyer here.
PUBLIC_BASE_URL_KEY = "public_base_url"
PROMPT_MODE_DEFAULT = "all"
# What the administrator sees for each way of combining the lesson prompt.
MODE_LABELS = {
    "student": "فقط پرامپت دانش‌آموز",
    "general": "فقط پرامپت عمومی",
    "student_db": "پرامپت دانش‌آموز همراه با اطلاعات دیتابیس",
    "all": "ترکیب تمام پرامپت‌ها و اطلاعات دیتابیس",
}


def get_setting(db: DBSession, key: str, default: str = "") -> str:
    row = db.get(AppSetting, key)
    return row.value if row and row.value != "" else default


def set_setting(db: DBSession, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value, updated_at=utcnow()))
    else:
        row.value = value
        row.updated_at = utcnow()
# How long a prompt token stays valid, in seconds. The conversation module reads it when a token is made.
PROMPT_TOKEN_TTL_KEY = "conversation_prompt_ttl_seconds"

# The language model the admin panel chooses. Empty values fall back to the environment.
AI_PROVIDER_KEY = "ai_provider"  # anthropic or openai (any OpenAI-compatible service)
AI_BASE_URL_KEY = "ai_base_url"  # only for the OpenAI-compatible provider
AI_MODEL_KEY = "ai_model"
AI_API_KEY_KEY = "ai_api_key"  # secret: shown masked only
