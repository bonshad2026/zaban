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
