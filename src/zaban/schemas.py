from typing import Literal

from pydantic import BaseModel, Field

LessonMinutes = Literal[5, 10, 15, 20, 30, 45, 60]
AgeBand = Literal["7-10", "11-14", "15-18", "adult"]
USERNAME_PATTERN = r"^[a-z0-9_.-]{3,30}$"


class StudentCreate(BaseModel):
    age_band: AgeBand
    display_name: str = Field(default="", max_length=120)
    external_user_id: str | None = Field(default=None, min_length=1, max_length=120)
    username: str | None = Field(default=None, pattern=USERNAME_PATTERN)
    password: str | None = Field(default=None, min_length=6, max_length=100)


class StudentUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    age_band: AgeBand | None = None


class PasswordSet(BaseModel):
    password: str = Field(min_length=6, max_length=100)


class ConsentCreate(BaseModel):
    accepted: bool
    text_version: str = Field(default="v1", max_length=20)


class PlacementCreate(BaseModel):
    score: int = Field(ge=0, le=100)


class PlanCreate(BaseModel):
    goal: str = Field(min_length=3, max_length=300)
    months: int = Field(ge=1, le=12)
    sessions_per_week: int = Field(ge=1, le=7)
    minutes_per_session: LessonMinutes


class SessionCreate(BaseModel):
    duration_minutes: LessonMinutes


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=500)


class StudentTokenRequest(BaseModel):
    student_id: str


class StudentLogin(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=100)


class ParentLogin(BaseModel):
    email: str = Field(min_length=3, max_length=190)
    password: str = Field(min_length=1, max_length=100)
