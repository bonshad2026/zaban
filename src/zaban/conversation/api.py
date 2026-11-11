import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from zaban.api import _require_complete_profile, _require_consent, _require_student_plan
from zaban.conversation import service
from zaban.conversation.models import ConvMessage, Conversation
from zaban.db import SessionLocal, get_db
from zaban.models import Guardian, Student, Tenant
from zaban.security import Auth, get_student_for_auth, require_tenant, require_manager
from zaban.services.ai_gateway import stream_complete
from zaban.services.metering import ensure_quota, record_usage
from zaban.services.payments import charge_plan_tokens, has_active_plan, require_plan

# A separate module: the server builds the instruction, the caller gets a token, and the conversation runs on that token.
# Routes are under /v1/conv so this part can be moved or reused without touching the lesson routes.
router = APIRouter(prefix="/conv")


class PromptRequest(BaseModel):
    duration_minutes: int = Field(default=10, ge=1, le=120)


class ConversationCreate(BaseModel):
    prompt_token: str = Field(min_length=10, max_length=600)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Conversation token is missing")
    return authorization[len("Bearer "):].strip()


def _owner(db: DBSession, student_id: str) -> Guardian | None:
    # The adult who pays for this learner. Their plan tokens are used by the conversation, as in a lesson.
    student = db.get(Student, student_id)
    owner_id = (student.guardian_id or student.self_owner_id) if student else None
    return db.get(Guardian, owner_id) if owner_id else None


@router.post("/students/{student_id}/prompt", status_code=201)
def make_prompt(
    student_id: str,
    body: PromptRequest,
    auth: Auth = Depends(require_manager),
    db: DBSession = Depends(get_db),
) -> dict:
    # Step 1: the lesson rules for one learner. The text stays on the server; only a token comes back.
    student = get_student_for_auth(db, auth, student_id)
    _require_consent(db, student)
    _require_student_plan(db, student)
    _require_complete_profile(db, student)
    ensure_quota(auth.tenant)
    token, expires_at = service.make_prompt_token(db, auth.tenant, student, body.duration_minutes)
    return {"prompt_token": token, "expires_at": expires_at}


@router.post("/conversations", status_code=201)
def open_conversation(
    body: ConversationCreate,
    tenant: Tenant = Depends(require_tenant),
    db: DBSession = Depends(get_db),
) -> dict:
    # Step 2: opens a conversation from a prompt token. The token works once.
    conversation, token = service.start_conversation(db, tenant, body.prompt_token)
    return {"conversation_id": conversation.id, "conversation_token": token, "expires_at": conversation.expires_at.isoformat()}


def _event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _reply_stream(conversation_id: str, tenant_id: str, text: str) -> Iterator[str]:
    # Runs after the response has started, so it opens its own database session.
    db = SessionLocal()
    try:
        conversation = db.get(Conversation, conversation_id)
        tenant = db.get(Tenant, tenant_id)
        messages = service.history(db, conversation) + [{"role": "user", "content": text}]
        usage: dict = {}
        pieces: list[str] = []
        for piece in stream_complete(conversation.text, messages, usage):
            pieces.append(piece)
            yield _event({"delta": piece})
        reply = "".join(pieces).strip()
        db.add(ConvMessage(conversation_id=conversation.id, role="user", content=text))
        db.add(ConvMessage(conversation_id=conversation.id, role="assistant", content=reply))
        record_usage(db, tenant, conversation.id, usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        # The learner's adult pays for the lesson tokens, the same as in a lesson. When the plan is used up, the conversation stops.
        owner = _owner(db, conversation.student_id)
        closed = False
        if owner is not None:
            charge_plan_tokens(db, owner, usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
            closed = not has_active_plan(owner)
        db.commit()
        yield _event({"done": True, "plan_finished": closed})
    except Exception:
        db.rollback()
        yield _event({"error": "The reply could not be finished. Please try again."})
    finally:
        db.close()


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: str,
    body: MessageIn,
    authorization: str | None = Header(default=None),
    db: DBSession = Depends(get_db),
) -> StreamingResponse:
    # Step 3, repeated for every turn: the reply is streamed as it is written.
    conversation = service.conversation_for_token(db, conversation_id, _bearer(authorization))
    if conversation.status != "active":
        raise HTTPException(status_code=409, detail="This conversation has ended")
    tenant = db.get(Tenant, conversation.tenant_id)
    ensure_quota(tenant)
    owner = _owner(db, conversation.student_id)
    if owner is not None:
        require_plan(owner)
    return StreamingResponse(
        _reply_stream(conversation.id, tenant.id, body.text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations/{conversation_id}/messages")
def read_messages(
    conversation_id: str,
    authorization: str | None = Header(default=None),
    db: DBSession = Depends(get_db),
) -> list[dict]:
    # Lets the page show the conversation again after a reload, while it is still kept.
    conversation = service.conversation_for_token(db, conversation_id, _bearer(authorization))
    return service.history(db, conversation)


@router.post("/conversations/{conversation_id}/end")
def end(
    conversation_id: str,
    authorization: str | None = Header(default=None),
    db: DBSession = Depends(get_db),
) -> dict:
    conversation = service.conversation_for_token(db, conversation_id, _bearer(authorization))
    service.end_conversation(db, conversation)
    return {"ok": True, "status": conversation.status}
