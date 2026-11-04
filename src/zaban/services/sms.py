from typing import Protocol

import httpx

from zaban.config import settings


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


def get_sms_sender() -> SmsSender:
    if settings.kavenegar_api_key:
        return KavenegarSms(settings.kavenegar_api_key, settings.kavenegar_otp_template)
    if settings.environment == "production":
        raise RuntimeError("KAVENEGAR_API_KEY is required in production")
    return _dev_sms


def dev_outbox() -> list[tuple[str, str]]:
    return _dev_sms.outbox
