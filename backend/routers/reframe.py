import asyncio

from fastapi import APIRouter, HTTPException

from schemas.reframe import ReframeRequest, ReframeResponse, SafetyResponse
from services import ai_service, safety_service


router = APIRouter(prefix="/api", tags=["reframe"])


@router.post("/reframe", response_model=ReframeResponse | SafetyResponse)
async def reframe(request: ReframeRequest) -> ReframeResponse | SafetyResponse:
    try:
        if safety_service.is_clearly_urgent(request.text):
            return SafetyResponse()
        # Keep the blocking HTTP request off FastAPI's event loop.
        return await asyncio.to_thread(ai_service.reframe, request.text)
    except ai_service.AIServiceUnavailable:
        raise HTTPException(
            status_code=503,
            detail="خدمة المساعدة الآلية غير متاحة حالياً. يرجى المحاولة لاحقاً.",
        ) from None
    except Exception:
        # Do not log the exception: a future service may include user text in it.
        raise HTTPException(
            status_code=500,
            detail="تعذر معالجة الطلب. يرجى المحاولة لاحقاً.",
        ) from None
