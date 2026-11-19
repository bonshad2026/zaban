import os

import pytest

from zaban.config import settings
from zaban.db import SessionLocal
from zaban.services import sms
from zaban.services.settings_store import (
    CONTACT_EMAIL_KEY,
    CONTACT_PHONE_KEY,
    PRICE_INPUT_KEY,
    PRICE_OUTPUT_KEY,
    SMS_API_KEY_KEY,
    SMS_PROVIDER_KEY,
    default_prices,
    set_setting,
)

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

# Service keys, prices and contact details are set in the admin panel and stored in the database. These tests check
# that the environment no longer carries them, and that the panel values reach the pages that use them.


@pytest.fixture(autouse=True)
def _restore_panel_values(client):
    # The client starts the app, which creates the tables before the panel values are read.
    yield
    with SessionLocal() as db:
        for key in (CONTACT_PHONE_KEY, CONTACT_EMAIL_KEY, PRICE_INPUT_KEY, PRICE_OUTPUT_KEY, SMS_API_KEY_KEY, SMS_PROVIDER_KEY):
            set_setting(db, key, "")
        db.commit()


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def test_the_settings_object_has_no_service_values():
    for name in (
        "kavenegar_api_key",
        "kavenegar_otp_template",
        "zarinpal_merchant_id",
        "payment_gateway",
        "anthropic_api_key",
        "model",
        "ai_provider",
        "openai_api_key",
        "input_price_per_mtok",
        "output_price_per_mtok",
        "contact_phone",
        "contact_email",
    ):
        assert name not in settings.__dataclass_fields__, name
    # The address and the OTP lifetime still come from the environment.
    assert settings.public_base_url
    assert settings.otp_ttl_seconds > 0


def test_prices_and_contact_details_are_saved_in_the_panel_and_used(client):
    _admin(client)
    saved = client.post("/v1/admin/api/connections", json={"price_input_per_mtok": 2.5, "price_output_per_mtok": 9.0})
    assert saved.status_code == 200, saved.text
    data = client.get("/v1/admin/api/connections").json()
    assert data["price_input_per_mtok"] == "2.5"
    assert data["price_output_per_mtok"] == "9.0"
    with SessionLocal() as db:
        assert default_prices(db) == (2.5, 9.0)

    details = client.post("/v1/admin/api/settings", json={"contact_phone": "02112345678", "contact_email": "help@example.com"})
    assert details.status_code == 200, details.text
    page = client.get("/contact").text
    assert "02112345678" in page and "help@example.com" in page


def test_the_site_address_is_read_from_the_environment_only(client):
    _admin(client)
    data = client.get("/v1/admin/api/connections").json()
    assert data["site_address"] == settings.public_base_url
    assert data["callback_url"] == f"{settings.public_base_url}/v1/web/billing/zarinpal/callback"


def test_production_sms_needs_the_key_in_the_panel():
    previous = settings.environment
    object.__setattr__(settings, "environment", "production")
    try:
        with SessionLocal() as db:
            set_setting(db, SMS_PROVIDER_KEY, "")
            set_setting(db, SMS_API_KEY_KEY, "")
            db.commit()
            with pytest.raises(RuntimeError):
                sms.get_sms_sender(db)
    finally:
        object.__setattr__(settings, "environment", previous)



def test_a_new_install_without_panel_values_still_runs(client):
    # Nothing is set in the panel: the public pages, the sign-in code and the AI reply all keep working.
    assert client.get("/contact").status_code == 200
    assert client.get("/login").status_code == 200
    assert client.post("/v1/web/user/otp/request", json={"phone": "09121239901", "purpose": "signup"}).status_code == 200
    from zaban.services.ai_gateway import current_config

    assert current_config().ready is False


def test_production_without_an_sms_key_is_a_clean_error_not_a_crash(client):
    previous = settings.environment
    object.__setattr__(settings, "environment", "production")
    try:
        response = client.post("/v1/web/user/otp/request", json={"phone": "09121239902", "purpose": "signup"})
        assert response.status_code == 502
        assert "SMS" in response.json()["detail"]
    finally:
        object.__setattr__(settings, "environment", previous)
