import hashlib
import hmac
import re
import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session as DBSession

from zaban.config import settings
from zaban.models import OtpCode, utcnow
from zaban.services.sms import get_sms_sender

RESEND_SECONDS = 60
MAX_CODES_PER_PHONE_PER_HOUR = 5
MAX_CODES_PER_IP_PER_HOUR = 20
MAX_ATTEMPTS_PER_CODE = 5

_PHONE_PATTERN = re.compile(r"^09\d{9}$")
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_phone(raw: str) -> str | None:
    # Accepts 09…, +98 9…, 0098 9… and Persian digits. Returns 09… or None.
    digits = re.sub(r"[\s\-()]", "", raw.translate(_PERSIAN_DIGITS))
    if digits.startswith("+"):
        digits = digits[1:]
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits
    return digits if _PHONE_PATTERN.match(digits) else None


def _hash_code(phone: str, code: str) -> str:
    return hmac.new(settings.secret_key.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def request_code(db: DBSession, phone: str, ip: str | None) -> None:
    now = utcnow()
    last = db.query(OtpCode).filter(OtpCode.phone == phone).order_by(OtpCode.created_at.desc()).first()
    if last and (now - last.created_at).total_seconds() < RESEND_SECONDS:
        raise HTTPException(status_code=429, detail="Please wait a minute before asking for another code")

    hour_ago = now - timedelta(hours=1)
    phone_count = db.query(OtpCode).filter(OtpCode.phone == phone, OtpCode.created_at >= hour_ago).count()
    if phone_count >= MAX_CODES_PER_PHONE_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many codes requested. Try again later")
    if ip:
        ip_count = db.query(OtpCode).filter(OtpCode.request_ip == ip, OtpCode.created_at >= hour_ago).count()
        if ip_count >= MAX_CODES_PER_IP_PER_HOUR:
            raise HTTPException(status_code=429, detail="Too many codes requested. Try again later")

    code = f"{secrets.randbelow(10**6):06d}"
    db.add(
        OtpCode(
            phone=phone,
            code_hash=_hash_code(phone, code),
            request_ip=ip,
            expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
        )
    )
    db.commit()
    try:
        get_sms_sender().send_otp(phone, code)
    except RuntimeError:
        raise HTTPException(status_code=502, detail="The SMS could not be sent. Please try again")


def check_code(db: DBSession, phone: str, code: str) -> bool:
    now = utcnow()
    record = (
        db.query(OtpCode)
        .filter(OtpCode.phone == phone, OtpCode.consumed_at.is_(None), OtpCode.expires_at > now)
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if record is None or record.attempts >= MAX_ATTEMPTS_PER_CODE:
        raise HTTPException(status_code=401, detail="Invalid or expired code. Request a new one")

    record.attempts += 1
    if not hmac.compare_digest(record.code_hash, _hash_code(phone, code.strip())):
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid or expired code. Request a new one")

    record.consumed_at = now
    db.commit()
    return True
