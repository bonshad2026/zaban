from fastapi import HTTPException
from sqlalchemy.orm import Session

from zaban.models import Tenant, Usage
from zaban.services.ai import estimate_cost


def ensure_quota(tenant: Tenant) -> None:
    if tenant.used_tokens >= tenant.quota_tokens:
        raise HTTPException(status_code=402, detail="Token quota exhausted")


def record_usage(db: Session, tenant: Tenant, session_id: str, input_tokens: int, output_tokens: int) -> None:
    tenant.used_tokens += input_tokens + output_tokens
    db.add(
        Usage(
            tenant_id=tenant.id,
            session_id=session_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_cost(input_tokens, output_tokens),
        )
    )
