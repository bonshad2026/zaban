from typing import Protocol

import httpx

from sqlalchemy.orm import Session as DBSession

from zaban.config import settings
from zaban.services.settings_store import DEFAULT_SMS_TEMPLATE, SMS_API_KEY_KEY, SMS_PROVIDER_KEY, SMS_TEMPLATE_KEY, get_setting


class SmsSender(Protocol):
    def send_otp(self, phone: str, code: str) -> None: ...


class KavenegarSms:
    # Kavenegar "verify lookup" sends the code through a template that Kavenegar has approved.
    URL = "https://api.kavenegar.com/v1/{key}/verify/lookup.json"

    def __init__(self, api_key: str, template: str) -> None:
        self._url = self.URL.format(key=api_key)
        self._template = template

    def send_otp(self, phone: str, code: str) -> None:
        response = httpx.get(
            self._url,
            params={"receptor": phone, "token": code, "template": self._template},
            timeout=10,
        )
        if response.status_code != 200:
            # Never include the phone number or the code in the error text.
            raise RuntimeError(f"SMS provider returned HTTP {response.status_code}")


class DevSms:
    # Development and tests only. Codes are kept in memory and never written to a log.
    def __init__(self) -> None:
        self.outbox: list[tuple[str, str]] = []

    def send_otp(self, phone: str, code: str) -> None:
        self.outbox.append((phone, code))


_dev_sms = DevSms()


def get_sms_sender(db: DBSession | None = None) -> SmsSender:
    # Every value comes from the administrator's panel.
    provider = get_setting(db, SMS_PROVIDER_KEY) if db is not None else ""
    if provider == "dev" and settings.environment != "production":
        return _dev_sms
    api_key = get_setting(db, SMS_API_KEY_KEY) if db is not None else ""
    template = (get_setting(db, SMS_TEMPLATE_KEY) if db is not None else "") or DEFAULT_SMS_TEMPLATE
    if api_key and provider != "dev":
        return KavenegarSms(api_key, template)
    if settings.environment == "production":
        raise RuntimeError("The SMS key is not set in the admin panel")
    return _dev_sms


def sms_provider_for(db: DBSession) -> str:
    # The provider the panel is set to. Until the panel is set, the development sender is used outside production.
    chosen = get_setting(db, SMS_PROVIDER_KEY)
    if chosen:
        return chosen
    return "kavenegar" if get_setting(db, SMS_API_KEY_KEY) else "dev"


def dev_outbox() -> list[tuple[str, str]]:
    return _dev_sms.outbox
