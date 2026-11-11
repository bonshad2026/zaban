from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from zaban.db import Base
from zaban.models import new_id, utcnow


# The instruction text for one conversation. It is made on the server and never sent to the client.
# The client only gets a token that points at this row, and the token works once.
class ConvPrompt(Base):
    __tablename__ = "conv_prompts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Conversation(Base):
    __tablename__ = "conv_conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("conv_prompts.id"))
    text: Mapped[str] = mapped_column(Text)  # the instruction copied from the prompt when the conversation starts
    status: Mapped[str] = mapped_column(String(20), default="active")  # active or ended
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # The conversation and all its messages are removed after this time (24 hours after it started).
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class ConvMessage(Base):
    __tablename__ = "conv_messages"

    # A number, so the messages keep the order they were written in.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conv_conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user or assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
