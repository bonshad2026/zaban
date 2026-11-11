import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

from zaban.config import settings

# A token is a signed, short note: what it points to, and when it stops working. Nothing secret is inside it.
PROMPT = "p"  # points to a prompt, used once to start a conversation
CONVERSATION = "c"  # points to a conversation, used for its turns


def _sign(body: str) -> str:
    digest = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def make_token(kind: str, item_id: str, expires_at: datetime) -> str:
    payload = {"k": kind, "id": item_id, "exp": int(expires_at.replace(tzinfo=UTC).timestamp())}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{body}.{_sign(body)}"


def read_token(token: str, kind: str) -> str | None:
    # Returns the id the token points to, or None when the token is wrong, of another kind, or expired.
    try:
        body, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(body)):
        return None
    padded = body + "=" * (-len(body) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("k") != kind:
        return None
    if payload.get("exp", 0) < datetime.now(UTC).timestamp():
        return None
    return payload.get("id")

