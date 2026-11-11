from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session as DBSession

from zaban.conversation import tokens
from zaban.conversation.models import ConvMessage, ConvPrompt, Conversation
from zaban.models import Student, Tenant, utcnow
from zaban.services.prompt_template import get_template, learner_values, render
from zaban.services.settings_store import PROMPT_TOKEN_TTL_KEY, get_setting

# A conversation and its messages are removed this long after it started.
RETENTION = timedelta(hours=24)
DEFAULT_PROMPT_TTL_SECONDS = 3600
MIN_PROMPT_TTL_SECONDS = 60
MAX_PROMPT_TTL_SECONDS = 86400


def prompt_ttl_seconds(db: DBSession) -> int:
    # The administrator sets this in the panel. An unusable value falls back to one hour.
    try:
        value = int(get_setting(db, PROMPT_TOKEN_TTL_KEY, str(DEFAULT_PROMPT_TTL_SECONDS)))
    except ValueError:
        value = DEFAULT_PROMPT_TTL_SECONDS
    return min(max(value, MIN_PROMPT_TTL_SECONDS), MAX_PROMPT_TTL_SECONDS)


def make_prompt_token(db: DBSession, tenant: Tenant, student: Student, duration_minutes: int) -> tuple[str, str]:
    # The instruction text is built here and stored on the server. The caller only receives a token for it.
    text, _ = render(get_template(db), learner_values(db, student, duration_minutes))
    expires_at = utcnow() + timedelta(seconds=prompt_ttl_seconds(db))
    row = ConvPrompt(tenant_id=tenant.id, student_id=student.id, text=text, expires_at=expires_at)
    db.add(row)
    db.commit()
    return tokens.make_token(tokens.PROMPT, row.id, expires_at), expires_at.isoformat()


def start_conversation(db: DBSession, tenant: Tenant, prompt_token: str) -> tuple[Conversation, str]:
    now = utcnow()
    prompt_id = tokens.read_token(prompt_token, tokens.PROMPT)
    prompt = db.get(ConvPrompt, prompt_id) if prompt_id else None
    if prompt is None or prompt.tenant_id != tenant.id or prompt.expires_at < now:
        raise HTTPException(status_code=401, detail="Prompt token is not valid")
    if prompt.used_at is not None:
        raise HTTPException(status_code=409, detail="This prompt token was already used")
    purge_expired(db)
    prompt.used_at = now
    conversation = Conversation(
        tenant_id=tenant.id,
        student_id=prompt.student_id,
        prompt_id=prompt.id,
        text=prompt.text,
        expires_at=now + RETENTION,
    )
    db.add(conversation)
    db.commit()
    return conversation, tokens.make_token(tokens.CONVERSATION, conversation.id, conversation.expires_at)


def conversation_for_token(db: DBSession, conversation_id: str, conversation_token: str) -> Conversation:
    # A conversation token works for its own conversation only.
    token_id = tokens.read_token(conversation_token, tokens.CONVERSATION)
    if token_id is None or token_id != conversation_id:
        raise HTTPException(status_code=401, detail="Conversation token is not valid")
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.expires_at < utcnow():
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def history(db: DBSession, conversation: Conversation) -> list[dict]:
    rows = (
        db.query(ConvMessage)
        .filter(ConvMessage.conversation_id == conversation.id)
        .order_by(ConvMessage.id)
        .all()
    )
    return [{"role": row.role, "content": row.content} for row in rows]


def end_conversation(db: DBSession, conversation: Conversation) -> None:
    # The conversation is closed now. Its messages stay for the retention period and are then removed.
    if conversation.status != "ended":
        conversation.status = "ended"
        conversation.ended_at = utcnow()
        db.commit()


def purge_expired(db: DBSession) -> int:
    # Removes conversations past their retention with their messages and prompt, and prompts that were never used and have expired.
    now = utcnow()
    expired = db.query(Conversation.id, Conversation.prompt_id).filter(Conversation.expires_at < now).all()
    conversation_ids = [row.id for row in expired]
    prompt_ids = [row.prompt_id for row in expired]
    if conversation_ids:
        db.query(ConvMessage).filter(ConvMessage.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
        db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).delete(synchronize_session=False)
    if prompt_ids:
        db.query(ConvPrompt).filter(ConvPrompt.id.in_(prompt_ids)).delete(synchronize_session=False)
    db.query(ConvPrompt).filter(ConvPrompt.expires_at < now, ConvPrompt.used_at.is_(None)).delete(synchronize_session=False)
    db.commit()
    return len(conversation_ids)
