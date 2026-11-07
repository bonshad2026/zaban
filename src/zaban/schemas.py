from typing import Literal

from pydantic import BaseModel, Field, model_validator

LessonMinutes = Literal[5, 10, 15, 20, 30, 45, 60]
AgeBand = Literal["4-6", "7-10", "11-14", "15-18", "adult"]
USERNAME_PATTERN = r"^[a-z0-9_.-]{3,30}$"


class StudentCreate(BaseModel):
    age_band: AgeBand
    display_name: str = Field(default="", max_length=120)
    external_user_id: str | None = Field(default=None, min_length=1, max_length=120)
    username: str | None = Field(default=None, pattern=USERNAME_PATTERN)
    # Guardians set a 4 to 6 digit PIN. Tenant API keys may send a longer password.
    password: str | None = Field(default=None, min_length=4, max_length=100)
    # Optional facts the lessons use to choose topics. A parent fills these in when creating a child's account.
    interests: str | None = Field(default=None, max_length=300)
    motivation: str | None = Field(default=None, max_length=60)
    # The learning goal from the fixed list (see program_data.GOALS). Empty means the everyday conversation program.
    goal: Literal["daily_conversation", "school", "travel", "work", "hobbies"] | None = None


class StudentUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    age_band: AgeBand | None = None


class PasswordSet(BaseModel):
    password: str = Field(min_length=4, max_length=100)


class ConsentCreate(BaseModel):
    accepted: bool
    text_version: str = Field(default="v1", max_length=20)


class PlacementCreate(BaseModel):
    # Either a level picked by the parent (A1 to C2), or a 0 to 100 score from a test.
    level: Literal["A1", "A2", "B1", "B2", "C1", "C2"] | None = None
    score: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def one_of_level_or_score(self) -> "PlacementCreate":
        if (self.level is None) == (self.score is None):
            raise ValueError("Send either a level or a score")
        return self


class PlanCreate(BaseModel):
    goal: str = Field(min_length=3, max_length=300)
    months: int = Field(ge=1, le=12)
    sessions_per_week: int = Field(ge=1, le=7)
    minutes_per_session: LessonMinutes


class SessionCreate(BaseModel):
    duration_minutes: LessonMinutes
    # Optional. When empty, the next suitable topic from the curriculum is chosen.
    topic_id: str | None = Field(default=None, max_length=40)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class StudentTokenRequest(BaseModel):
    student_id: str


class AccentChoice(BaseModel):
    accent: Literal["en-US", "en-GB", "en-AU", "en-CA"]


class LevelTestAnswers(BaseModel):
    # One chosen option index per question, in the same order as the questions.
    answers: list[int] = Field(min_length=6, max_length=6)


class StudentLogin(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=100)


class OtpRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=24)
    purpose: Literal["signup", "reset"] = "signup"


class SignUpCreate(BaseModel):
    phone: str = Field(min_length=6, max_length=24)
    code: str = Field(min_length=4, max_length=8, pattern=r"^\d{4,8}$")
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=100)
    age_confirmed: bool
    goal: str | None = Field(default=None, max_length=60)


class UserLogin(BaseModel):
    phone: str = Field(min_length=6, max_length=24)
    password: str = Field(min_length=1, max_length=100)


class PasswordReset(BaseModel):
    phone: str = Field(min_length=6, max_length=24)
    code: str = Field(min_length=4, max_length=8, pattern=r"^\d{4,8}$")
    password: str = Field(min_length=8, max_length=100)


# A PIN is what a child types on a phone or tablet, so it is 4 to 6 digits.
PIN_PATTERN = r"^\d{4,6}$"


class VoiceSampleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    accent: Literal["en-US", "en-GB", "en-AU", "en-CA"]
    mime: Literal["audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4"]
    # The file as base64, so no separate upload parser is needed. The server limits the decoded size.
    data_base64: str = Field(min_length=4, max_length=7_000_000)
