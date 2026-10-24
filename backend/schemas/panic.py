from typing import Literal

from pydantic import BaseModel, Field


class PanicRequest(BaseModel):
    step: int = Field(strict=True, ge=1, le=5)
    text: str | None = Field(default=None, max_length=1000)
    action: Literal["continue", "skip", "stop"] = Field(
        default="continue",
        description="Skip advances without an answer; stop ends the exercise.",
    )


class PanicResponse(BaseModel):
    reply: str
    emergency: bool = False
    completed: bool = False
