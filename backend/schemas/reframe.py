from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class OllamaAnalysis(BaseModel):
    """Validate generated content before exposing it through the public API."""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    distortion_key: Literal[
        "Catastrophizing", "Overgeneralization", "Labeling", "All-or-Nothing",
        "Mind Reading", "Balanced",
    ]
    reality_check: str = Field(min_length=1, max_length=1000)
    reframed_thought: str = Field(min_length=1, max_length=1000)


class OllamaGenerateResponse(BaseModel):
    response: str = Field(strict=True, min_length=1)


class SafetyResponse(BaseModel):
    emergency: Literal[True] = True
    message: str = "إذا كنت في خطر مباشر، اطلب مساعدة بشرية أو اتصل بالطوارئ."
    helpline: str = "911"
