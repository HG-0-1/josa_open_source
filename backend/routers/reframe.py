from fastapi import APIRouter, HTTPException

from schemas.reframe import ReframeRequest, ReframeResponse, SafetyResponse
from services import ai_service, safety_service


router = APIRouter(prefix="/api", tags=["reframe"])


@router.post("/reframe", response_model=ReframeResponse | SafetyResponse)
async def reframe(request: ReframeRequest) -> ReframeResponse | SafetyResponse:
    try:
        if safety_service.is_clearly_urgent(request.text):
            return SafetyResponse()
        return ai_service.reframe(request.text)
    except Exception:
        # Do not log the exception: a future service may include user text in it.
        raise HTTPException(
            status_code=500,
            detail="تعذر معالجة الطلب. يرجى المحاولة لاحقاً.",
        ) from None
