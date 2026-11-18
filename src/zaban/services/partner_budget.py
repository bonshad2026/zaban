# Plan tokens and dates during a lesson (docs/conversation-partner.md, section 13.7).
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from zaban.models import Guardian
from zaban.services.partner_settings import partner_value


def tokens_left(owner: Guardian) -> int:
    return max(0, owner.plan_token_allowance - owner.plan_tokens_used)


def reserve_reached(db: DBSession, owner: Guardian | None) -> bool:
    # The reserve is kept for the end-of-lesson routine. When the rest of the plan reaches it, the lesson closes.
    if owner is None:
        return False
    return tokens_left(owner) <= int(partner_value(db, "partner_token_reserve"))


def remaining_percent(owner: Guardian) -> int:
    if owner.plan_token_allowance <= 0:
        return 100
    return max(0, 100 - round(owner.plan_tokens_used * 100 / owner.plan_token_allowance))


def warnings(db: DBSession, owner: Guardian | None, now: datetime) -> list[dict]:
    # Shown to the learner: a token warning when the tokens left reach a threshold set by the administrator,
    # and a warning close to the plan's end date.
    if owner is None:
        return []
    out = []
    if owner.plan_token_allowance > 0:
        left = remaining_percent(owner)
        thresholds = [int(p) for p in partner_value(db, "partner_token_warn_remaining").split(",") if p.strip()]
        reached = [p for p in thresholds if left <= p]
        if reached:
            out.append({"kind": "tokens", "remaining_percent": left, "threshold": min(reached)})
    if owner.plan_expires_at is not None:
        remaining = (owner.plan_expires_at - now).total_seconds()
        if 0 < remaining <= int(partner_value(db, "partner_expiry_warn_days")) * 86400:
            out.append({"kind": "expiry", "days_left": int(remaining // 86400)})
    return out
