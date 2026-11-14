import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Table, Text, UniqueConstraint
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
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "female", "male" or "other". Empty means the adult has not said.
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # A small square photo as a data URL, resized in the browser before upload. Empty means no photo.
    avatar_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The adult's own 6-character referral code, and the adult whose code they used at sign-up (if any).
    referral_code: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    referred_by_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("guardians.id"), nullable=True, index=True)
    # The adult chosen as this adult's teacher, by their referral code. Empty means no teacher. Only one teacher at a time.
    teacher_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("guardians.id"), nullable=True, index=True)
    # Set at sign-up. Used with the phone number at sign-in. Forgotten passwords are reset with an SMS code.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # The account can use the service until this time. Empty means no plan has been activated yet.
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # When the current paid period began. A renewal before the old plan ends keeps this date.
    plan_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # The token allowance of the current plan, and how many tokens lessons have used so far.
    plan_token_allowance: Mapped[int] = mapped_column(Integer, default=0)
    # A suspended adult cannot sign in, and no page or lesson is open to them until the suspension is lifted.
    suspended: Mapped[bool] = mapped_column(default=False)
    plan_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
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
    last_name: Mapped[str] = mapped_column(String(120), default="")
    subject: Mapped[str] = mapped_column(String(160), default="")
    # The caller agrees to be phoned. The form does not send without it.
    contact_permission: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new, reviewed, called, recall, awaiting_reply, closed (old: contacted)
    request_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class BillingPlan(Base):
    # A plan an adult buys. Prices are in toman. A plan gives access for a number of days.
    __tablename__ = "billing_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    # The name shown when the page is in English. Empty means the Persian name is used.
    name_en: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    price_toman: Mapped[int] = mapped_column(Integer)
    days: Mapped[int] = mapped_column(Integer)
    # How many tokens (input and output together) the plan allows before it is used up.
    token_allowance: Mapped[int] = mapped_column(Integer, default=1_000_000)
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
    # Why the payment failed, in words the buyer can read. Empty when it did not fail.
    failure_reason: Mapped[str] = mapped_column(String(200), default="")
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
    # A finished topic the learner asked to play again in the next lesson. Cleared once that lesson has started.
    repeat_topic_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    username: Mapped[str | None] = mapped_column(String(60), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guardian_id: Mapped[str | None] = mapped_column(ForeignKey("guardians.id"), index=True, nullable=True)
    self_owner_id: Mapped[str | None] = mapped_column(ForeignKey("guardians.id"), index=True, nullable=True)
    age_band: Mapped[str] = mapped_column(String(20))
    cefr_level: Mapped[str | None] = mapped_column(String(4), nullable=True)
    # One level per skill. Each starts at A1 and is changed by the learner or by the level test of that skill.
    level_listening: Mapped[str] = mapped_column(String(4), default="A1")
    level_reading: Mapped[str] = mapped_column(String(4), default="A1")
    level_grammar: Mapped[str] = mapped_column(String(4), default="A1")
    level_speaking_writing: Mapped[str] = mapped_column(String(4), default="A1")
    # PIN login protection: after repeated wrong PINs the login is paused for a while.
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    guardian: Mapped[Guardian | None] = relationship(back_populates="students", foreign_keys=[guardian_id])
    consents: Mapped[list["Consent"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    plans: Mapped[list["Plan"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    sessions: Mapped[list["TutorSession"]] = relationship(back_populates="student", cascade="all, delete-orphan")


class TutorProfile(Base):
    # What the lesson prompt knows about one learner: interests and motivation (from the parent or sign-up form),
    # and notes an administrator writes. They shape topics and tone but never override the safety rules.
    # Kept in its own table, so an existing database gets it from create_all.
    __tablename__ = "tutor_profiles"

    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), primary_key=True)
    interests: Mapped[str] = mapped_column(Text, default="")
    motivation: Mapped[str] = mapped_column(String(60), default="")
    instructions: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AppSetting(Base):
    # One row per setting. Used for the general prompt that applies to every lesson.
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LearnerPreference(Base):
    # Choices the learner makes for themself, such as the English accent they practise.
    __tablename__ = "learner_preferences"

    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), primary_key=True)
    accent: Mapped[str] = mapped_column(String(10), default="en-US")


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
    # The short evaluation written after the lesson, shown in the learner progress and the parent report.
    evaluation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The system prompt built when the lesson started: admin guidance, database facts, the learner and the lesson item.
    start_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    # The model that answered, so the cost can be read against its price.
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class VoiceSample(Base):
    # A recorded sentence the administrator uploads for one accent. Learners hear it on the accent card.
    __tablename__ = "voice_samples"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    accent: Mapped[str] = mapped_column(String(10), index=True)
    mime: Mapped[str] = mapped_column(String(30))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CurriculumTopic(Base):
    # One conversation topic. Levels run from first_level to last_level, and bands lists the age band codes it fits (K, J, T, S, A).
    __tablename__ = "curriculum_topics"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    goal: Mapped[str] = mapped_column(Text)
    first_level: Mapped[str] = mapped_column(String(2))
    last_level: Mapped[str] = mapped_column(String(2))
    bands: Mapped[str] = mapped_column(String(10))
    # The order of the topics in the lesson path. Set by dragging in the admin panel.
    position: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class CurriculumPoint(Base):
    # A point the teacher wants to talk about in a topic's course. The admin lists them under the topic.
    __tablename__ = "curriculum_points"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    topic_id: Mapped[str] = mapped_column(ForeignKey("curriculum_topics.id"), index=True)
    text: Mapped[str] = mapped_column(String(300))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CurriculumVariant(Base):
    # The version of one topic for one age band and one level, such as INTRO.K.A1.
    __tablename__ = "curriculum_variants"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("curriculum_topics.id"), index=True)
    band: Mapped[str] = mapped_column(String(1))
    level: Mapped[str] = mapped_column(String(2))
    opener: Mapped[str] = mapped_column(Text, default="")
    phrases: Mapped[list] = mapped_column(JSON, default=list)
    style: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LessonTopic(Base):
    # Which topic and variant a lesson used, and the catalog version at that time. Old lessons keep their own record.
    __tablename__ = "lesson_topics"

    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("curriculum_topics.id"), index=True)
    variant_id: Mapped[str] = mapped_column(ForeignKey("curriculum_variants.id"))
    catalog_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StudentGoal(Base):
    # The goal a parent chose for a child, from the fixed list. Used to pick the learning program.
    __tablename__ = "student_goals"

    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), primary_key=True)
    goal: Mapped[str] = mapped_column(String(40))


class CooperationRequest(Base):
    # A public request from the cooperation form, for people who want to work with the company (not learners).
    __tablename__ = "cooperation_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(16))
    email: Mapped[str | None] = mapped_column(String(190), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="new")  # new, contacted, closed
    request_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


# A tag is a label on help content. The administrator defines the facets (groups such as «علایق») and their tags,
# and changes them later. Learners filter the help content by these tags.
help_content_tags = Table(
    "help_content_tags",
    Base.metadata,
    Column("content_id", String(32), ForeignKey("help_content.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(32), ForeignKey("help_tags.id", ondelete="CASCADE"), primary_key=True),
)


class HelpContent(Base):
    # A learning aid: a podcast, story, animation, video or sample. It is either a file stored in the database
    # (data and mime) or a link (url). Learners see only the items that match their age, level and interests.
    __tablename__ = "help_content"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(20))  # podcast, story, animation, video, sample, other
    age_band: Mapped[str] = mapped_column(String(1))  # K, J, T, S, A (same codes as the curriculum)
    level: Mapped[str] = mapped_column(String(2))
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)  # empty means for everyone
    interests: Mapped[str] = mapped_column(String(200), default="")  # comma-separated tags
    topic_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    stage: Mapped[str | None] = mapped_column(String(40), nullable=True)  # course stage, free text
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    tags: Mapped[list["HelpTag"]] = relationship(secondary=help_content_tags, order_by="HelpTag.sort_order")


class HelpFacet(Base):
    __tablename__ = "help_facets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(60))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    tags: Mapped[list["HelpTag"]] = relationship(
        back_populates="facet", cascade="all, delete-orphan", order_by="HelpTag.sort_order"
    )


class HelpTag(Base):
    __tablename__ = "help_tags"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    facet_id: Mapped[str] = mapped_column(ForeignKey("help_facets.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(60))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    facet: Mapped[HelpFacet] = relationship(back_populates="tags")


class SelfTest(Base):
    # An adult or learner's own test ("خودت رو محک بزن"). The config holds the choices the learner made.
    __tablename__ = "self_tests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # qa, conversation, mixed, suggested
    skill: Mapped[str] = mapped_column(String(20))  # writing, listening, speaking, mixed
    minutes: Mapped[int] = mapped_column(Integer)
    level_used: Mapped[str | None] = mapped_column(String(4), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, finished
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A score from 0 to 100 that Niko gives at the end. Empty for tests finished before scores existed.
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    messages: Mapped[list["SelfTestMessage"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="SelfTestMessage.id"
    )


class SelfTestMessage(Base):
    __tablename__ = "self_test_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("self_tests.id"), index=True)
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    test: Mapped[SelfTest] = relationship(back_populates="messages")


class LearnerDetails(Base):
    # Personal facts about a learner that shape the lesson prompt. Filled by the learner, or by the parent for a child.
    __tablename__ = "learner_details"

    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), primary_key=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(40), nullable=True)  # school grade, free text
    attributes: Mapped[str] = mapped_column(Text, default="")  # personality and what they like in a teacher
    conversation_style: Mapped[str | None] = mapped_column(String(20), nullable=True)  # chat, story, role_play, quiz, mixed
    response_style: Mapped[str | None] = mapped_column(String(20), nullable=True)  # gentle, direct, playful, strict
    level_sample: Mapped[str] = mapped_column(Text, default="")  # a sample of the learner's English or a level code
    free_text: Mapped[str] = mapped_column(Text, default="")  # anything else the learner wants Niko to know
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class WebSession(Base):
    # One row per sign-in on a device. The cookie carries its id, so an administrator can end a single sign-in.
    __tablename__ = "web_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    # "guardian" for an adult, "student" for a learner profile.
    role: Mapped[str] = mapped_column(String(10))
    subject_id: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    user_agent: Mapped[str] = mapped_column(String(200), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PlacementQuestion(Base):
    # One question of the level test. The bank is kept in the database and edited by the administrator.
    __tablename__ = "placement_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill: Mapped[str] = mapped_column(String(20), index=True)  # reading, grammar, listening
    level: Mapped[str] = mapped_column(String(4), index=True)  # A1 to C1
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[str] = mapped_column(Text)  # JSON list of choices
    answer: Mapped[int] = mapped_column(Integer)  # index of the correct choice
    audio_text: Mapped[str] = mapped_column(Text, default="")  # read aloud in the browser for listening items
    active: Mapped[bool] = mapped_column(default=True)


class PlacementAttempt(Base):
    # One sitting of one skill. It can be left and continued later, because the answers are stored as they are given.
    __tablename__ = "placement_attempts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    skill: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress, done, skipped
    level_index: Mapped[int] = mapped_column(Integer, default=0)
    answers: Mapped[str] = mapped_column(Text, default="[]")  # JSON list of answers given so far
    result_level: Mapped[str | None] = mapped_column(String(4), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

