from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ReframeRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000)

    @field_validator("text", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ReframeResponse(BaseModel):
    emergency: Literal[False] = False
    distortion: str
    reality_check: str
    reframed_thought: str


class SafetyResponse(BaseModel):
    emergency: Literal[True] = True
    message: str = "إذا كنت في خطر مباشر، اطلب مساعدة بشرية أو اتصل بالطوارئ."
    helpline: str = "911"
