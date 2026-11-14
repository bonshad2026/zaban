from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from zaban.models import Tenant, Usage
from zaban.services.ai import estimate_cost
from zaban.services.ai_gateway import current_config
from zaban.services.ai_models import prices_for


def ensure_quota(tenant: Tenant) -> None:
    if tenant.used_tokens >= tenant.quota_tokens:
        raise HTTPException(status_code=402, detail="Token quota exhausted")


def record_usage(db: Session, tenant: Tenant, session_id: str, input_tokens: int, output_tokens: int) -> None:
    # The cost uses the price of the model that is set in the admin panel. An offline reply costs nothing.
    config = current_config()
    cost = estimate_cost(input_tokens, output_tokens, prices_for(config.model)) if config.ready else 0.0
    tenant.used_tokens += input_tokens + output_tokens
    db.add(
        Usage(
            tenant_id=tenant.id,
            session_id=session_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            model=config.model if config.ready else None,
        )
    )


def session_usage(db: Session, session_id: str) -> dict:
    # Tokens and cost of every reply of one lesson.
    tokens, cost = (
        db.query(
            func.coalesce(func.sum(Usage.input_tokens + Usage.output_tokens), 0),
            func.coalesce(func.sum(Usage.cost_usd), 0.0),
        )
        .filter(Usage.session_id == session_id)
        .one()
    )
    return {"tokens": int(tokens), "cost_usd": round(float(cost), 6)}
