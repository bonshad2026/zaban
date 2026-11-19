from sqlalchemy.orm import Session as DBSession

from zaban.models import AppSetting, utcnow

# Every setting the administrator changes lives in the database, set in the admin panel. Nothing here reads the environment.
# A missing value uses the default below. Secrets are stored in the database and are only ever shown masked.
PAYMENT_PROVIDER_KEY = "payment_provider"  # fake, zarinpal
DEFAULT_PAYMENT_PROVIDER = "fake"
ZARINPAL_MERCHANT_KEY = "zarinpal_merchant_id"  # secret: shown masked only
SMS_PROVIDER_KEY = "sms_provider"  # kavenegar, dev
SMS_API_KEY_KEY = "sms_api_key"  # secret: shown masked only
SMS_TEMPLATE_KEY = "sms_otp_template"
DEFAULT_SMS_TEMPLATE = "zaban-otp"
CONTACT_PHONE_KEY = "contact_phone"
CONTACT_EMAIL_KEY = "contact_email"
PRICE_INPUT_KEY = "price_input_per_mtok"  # USD per million tokens, for models that are not in the list
PRICE_OUTPUT_KEY = "price_output_per_mtok"
DEFAULT_PRICE_INPUT = "1.0"
DEFAULT_PRICE_OUTPUT = "5.0"


def default_prices(db: DBSession) -> tuple[float, float]:
    # Input and output price per million tokens, used when the model is not in the list.
    return float(get_setting(db, PRICE_INPUT_KEY, DEFAULT_PRICE_INPUT)), float(get_setting(db, PRICE_OUTPUT_KEY, DEFAULT_PRICE_OUTPUT))
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

# The language model the admin panel chooses.
AI_PROVIDER_KEY = "ai_provider"  # anthropic or openai (any OpenAI-compatible service)
DEFAULT_AI_PROVIDER = "anthropic"
AI_BASE_URL_KEY = "ai_base_url"  # only for the OpenAI-compatible provider
DEFAULT_AI_BASE_URL = "https://api.openai.com/v1"
AI_MODEL_KEY = "ai_model"
DEFAULT_AI_MODEL = "claude-haiku-5-5"
AI_API_KEY_KEY = "ai_api_key"  # secret: shown masked only
