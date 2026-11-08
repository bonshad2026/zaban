from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from zaban.db import get_db
from zaban.security import Auth, get_auth
from zaban.services.ai_gateway import complete
from zaban.services.metering import ensure_quota, record_usage

# A stand-alone AI service for other systems. It is separate from the lesson and test features: the caller sends the
# whole prompt and the whole conversation each time, and the server keeps no state. Only tenant API keys may call it.
router = APIRouter(prefix="/ai")

MAX_TURNS = 40
MAX_CHARS = 4000


class AITurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_CHARS)


class AICompleteRequest(BaseModel):
    system: str = Field(min_length=1, max_length=MAX_CHARS * 2)
    messages: list[AITurn] = Field(min_length=1, max_length=MAX_TURNS)
    max_tokens: int = Field(default=300, ge=1, le=1000)


class AICompleteResponse(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int
    mode: str


@router.post("/complete", response_model=AICompleteResponse)
def ai_complete(body: AICompleteRequest, auth: Auth = Depends(get_auth), db: DBSession = Depends(get_db)) -> dict:
    if auth.student_id or auth.guardian_id:
        raise HTTPException(status_code=403, detail="This service needs a tenant API key")
    if body.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="The last message must come from the user")
    ensure_quota(auth.tenant)
    result = complete(body.system, [m.model_dump() for m in body.messages], max_tokens=body.max_tokens)
    record_usage(db, auth.tenant, "api", result.input_tokens, result.output_tokens)
    db.commit()
    return {
        "text": result.text,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "mode": result.mode,
    }
