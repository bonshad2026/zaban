import os

import pytest

from zaban.db import SessionLocal
from zaban.services import ai_gateway
from zaban.services.settings_store import AI_API_KEY_KEY, AI_BASE_URL_KEY, AI_MODEL_KEY, AI_PROVIDER_KEY, set_setting

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


@pytest.fixture(autouse=True)
def _restore_ai_settings():
    # These tests change the provider in the database. Put it back so other tests keep the offline reply.
    yield
    with SessionLocal() as db:
        for key in (AI_PROVIDER_KEY, AI_BASE_URL_KEY, AI_MODEL_KEY, AI_API_KEY_KEY):
            set_setting(db, key, "")
        db.commit()


def _admin(client) -> None:
    assert client.post("/v1/admin/api/login", json={"password": ADMIN_PASSWORD}).status_code == 200


def test_admin_saves_provider_address_model_and_key(client):
    _admin(client)
    saved = client.post(
        "/v1/admin/api/connections",
        json={
            "ai_provider": "openai",
            "ai_base_url": "https://api.example-provider.test/v1/",
            "ai_model": "example-model-1",
            "ai_api_key": "sk-test-0123456789abcdef",
        },
    )
    assert saved.status_code == 200, saved.text
    shown = client.get("/v1/admin/api/connections").json()
    assert shown["ai_provider"] == "openai"
    assert shown["ai_base_url"] == "https://api.example-provider.test/v1"
    assert shown["ai_model"] == "example-model-1"
    assert shown["ai_api_key_set"] is True
    assert "sk-test" not in shown["ai_api_key_masked"]
    with SessionLocal() as db:
        config = ai_gateway.current_config()
    assert config.provider == "openai" and config.model == "example-model-1" and config.ready


def test_bad_address_is_refused(client):
    _admin(client)
    response = client.post("/v1/admin/api/connections", json={"ai_base_url": "ftp://wrong.example"})
    assert response.status_code == 400


def test_empty_key_or_model_means_offline_reply(client):
    _admin(client)
    client.post("/v1/admin/api/connections", json={"ai_provider": "openai", "ai_model": " "})
    with SessionLocal() as db:
        set_setting(db, AI_API_KEY_KEY, "")
        set_setting(db, AI_MODEL_KEY, "")
    result = ai_gateway.complete("rules", [{"role": "user", "content": "hello"}])
    assert result.mode == "offline"
    with SessionLocal() as db:
        set_setting(db, AI_PROVIDER_KEY, "anthropic")
        set_setting(db, AI_BASE_URL_KEY, "")


def test_cost_uses_the_price_of_the_chosen_model(client):
    from zaban.models import Tenant, Usage
    from zaban.services.metering import record_usage, session_usage

    _admin(client)
    client.post("/v1/admin/api/connections", json={"ai_provider": "openai", "ai_model": "gpt-6-luna", "ai_api_key": "sk-test-0123456789abcdef"})
    with SessionLocal() as db:
        tenant = db.query(Tenant).first()
        record_usage(db, tenant, "session-price-check", 1_000_000, 0)
        db.commit()
        row = db.query(Usage).filter(Usage.session_id == "session-price-check").one()
        assert row.model == "gpt-6-luna"
        assert abs(row.cost_usd - 0.10) < 1e-9
        assert session_usage(db, "session-price-check")["tokens"] == 1_000_000
        db.delete(row)
        db.commit()
