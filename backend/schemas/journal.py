from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Mood = Literal["قلق", "حزن", "غضب", "فرح", "هدوء", "توتر"]
TriggerCategory = Literal["دراسة", "شغل", "عائلة", "علاقات", "صحة", "نوم", "غير ذلك"]


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        if value.count("@") != 1:
            raise ValueError("البريد الإلكتروني غير صالح")
        local, domain = value.split("@")
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("البريد الإلكتروني غير صالح")
        if any(char.isspace() for char in value):
            raise ValueError("البريد الإلكتروني غير صالح")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str


class AuthOut(BaseModel):
    authenticated: bool = True
    user: UserOut
    csrf_token: str


class AuthMeOut(BaseModel):
    authenticated: bool
    user: UserOut | None = None
    csrf_token: str | None = None


class JournalEntryCreate(BaseModel):
    mood: Mood
    intensity: int = Field(ge=1, le=5)
    trigger_category: TriggerCategory
    trigger_note: str | None = Field(default=None, max_length=500)
    journal_text: str | None = Field(default=None, max_length=5000)

    @field_validator("trigger_note", "journal_text", mode="before")
    @classmethod
    def trim_optional_text(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mood: Mood
    intensity: int
    trigger_category: TriggerCategory
    trigger_note: str | None
    journal_text: str | None
    created_at: str


class JournalEntriesOut(BaseModel):
    entries: list[JournalEntryOut]
    limit: int
    offset: int


class CountOut(BaseModel):
    label: str
    count: int


class IntensityPointOut(BaseModel):
    date: str
    mood: Mood
    intensity: int


class AssociationOut(BaseModel):
    mood: Mood
    trigger_category: TriggerCategory
    count: int


class JournalInsightsOut(BaseModel):
    days: Literal[7, 30]
    total_entries: int
    mood_counts: list[CountOut]
    trigger_counts: list[CountOut]
    intensity_trend: list[IntensityPointOut]
    associations: list[AssociationOut]
    pattern_notes: list[str]
    sufficient_data: bool


class AiInsightsRequest(BaseModel):
    consent: Literal[True]
    days: Literal[7, 30] = 30


class AiInsightsOut(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    pattern: str = Field(min_length=1, max_length=500)
    evidence: str = Field(min_length=1, max_length=500)
    suggestion: str = Field(min_length=1, max_length=500)
