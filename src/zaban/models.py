import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zaban.db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    # Stored as naive UTC so SQLite and PostgreSQL behave the same way.
    return datetime.now(UTC).replace(tzinfo=None)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    quota_tokens: Mapped[int] = mapped_column(Integer, default=0)
    used_tokens: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Guardian(Base):
    # An adult account, signed in with a mobile number and an SMS code. It can manage children
    # (guardian_id on Student) and can also learn for itself (self_owner_id on Student).
    __tablename__ = "guardians"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    phone: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(190), unique=True, nullable=True)
    # Set at sign-up. Used with the phone number at sign-in. Forgotten passwords are reset with an SMS code.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # The account can use the service until this time. Empty means no plan has been activated yet.
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # What the adult says they want to learn at sign-up (free text, short).
    goal: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Bumped on logout-everywhere and password reset, so older sign-in cookies stop working.
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    students: Mapped[list["Student"]] = relationship(back_populates="guardian", foreign_keys="Student.guardian_id")


class ConsultRequest(Base):
    # A public request from the consultation form. Nobody needs to sign in to send it.
    __tablename__ = "consult_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text, default="")
    preferred_time: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new, contacted, closed
    request_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class BillingPlan(Base):
    # A plan an adult buys. Prices are in toman. A plan gives access for a number of days.
    __tablename__ = "billing_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    price_toman: Mapped[int] = mapped_column(Integer)
    days: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(default=True)


class Payment(Base):
    # A payment request. It becomes "confirmed" only after the gateway reports success, checked on the server.
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    guardian_id: Mapped[str] = mapped_column(ForeignKey("guardians.id"), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("billing_plans.id"))
    amount_toman: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, confirmed, failed
    gateway: Mapped[str] = mapped_column(String(20), default="fake")
    gateway_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OtpCode(Base):
    # A one-time SMS code. Only its hash is stored.
    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(16), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    request_ip: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Student(Base):
    # A learner. Two kinds exist:
    # - managed: a child under 18, created by a guardian (guardian_id), signs in with username and PIN.
    # - self: an adult who learns for themself (self_owner_id). Only that adult can see their reports.
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("tenant_id", "external_user_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    external_user_id: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    username: Mapped[str | None] = mapped_column(String(60), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guardian_id: Mapped[str | None] = mapped_column(ForeignKey("guardians.id"), index=True, nullable=True)
    self_owner_id: Mapped[str | None] = mapped_column(ForeignKey("guardians.id"), index=True, nullable=True)
    age_band: Mapped[str] = mapped_column(String(20))
    cefr_level: Mapped[str | None] = mapped_column(String(4), nullable=True)
    # PIN login protection: after repeated wrong PINs the login is paused for a while.
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    guardian: Mapped[Guardian | None] = relationship(back_populates="students", foreign_keys=[guardian_id])
    consents: Mapped[list["Consent"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    plans: Mapped[list["Plan"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    sessions: Mapped[list["TutorSession"]] = relationship(back_populates="student", cascade="all, delete-orphan")


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    text_version: Mapped[str] = mapped_column(String(20))
    accepted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student: Mapped[Student] = relationship(back_populates="consents")


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    goal: Mapped[str] = mapped_column(Text)
    months: Mapped[int] = mapped_column(Integer)
    sessions_per_week: Mapped[int] = mapped_column(Integer)
    minutes_per_session: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[datetime] = mapped_column(DateTime)
    end_date: Mapped[datetime] = mapped_column(DateTime)
    milestones: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="active")

    student: Mapped[Student] = relationship(back_populates="plans")


class TutorSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    student: Mapped[Student] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    session: Mapped[TutorSession] = relationship(back_populates="messages")


class Usage(Base):
    # Billing record. It has no foreign key to sessions, so it survives when student data is deleted.
    __tablename__ = "usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
