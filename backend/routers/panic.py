from fastapi import APIRouter, HTTPException

from schemas.panic import PanicRequest, PanicResponse
from schemas.reframe import SafetyResponse
from services import grounding_service, safety_service


router = APIRouter(prefix="/api", tags=["grounding"])


@router.post("/panic", response_model=PanicResponse)
async def panic(request: PanicRequest) -> PanicResponse:
    """Optional grounding with limited, non-clinical preliminary safety routing."""
    try:
        text = request.text or ""
        # Emergency guidance always takes precedence, including on stop/skip.
        if safety_service.has_urgent_physical_symptoms(text):
            return PanicResponse(
                reply=(
                    "الألم الشديد بالصدر أو الصعوبة الشديدة بالتنفس يحتاجوا تقييم طبي عاجل. "
                    "أوقف التمرين واتصل بالطوارئ المحلية أو اطلب مساعدة طبية فوراً. "
                    "ما بنقدر نفترض إن السبب قلق."
                ),
                emergency=True,
            )
        if safety_service.is_clearly_urgent(text):
            return PanicResponse(reply=SafetyResponse().message, emergency=True)
        return grounding_service.next_guidance(request.step, text, request.action)
    except Exception:
        # Never log user text or exceptions that might contain it.
        raise HTTPException(
            status_code=500, detail="تعذر معالجة الطلب. يرجى المحاولة لاحقاً."
        ) from None
