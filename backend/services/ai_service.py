from schemas.reframe import ReframeResponse


def reframe(text: str) -> ReframeResponse:
    """Return a fixed mock response; no analysis, storage, or external calls."""
    return ReframeResponse(
        distortion="نمط تفكير محتمل: التعميم الزائد",
        reality_check="تجربة واحدة لا تحدد كل قدراتك.",
        reframed_thought="المقابلة ما نجحت، لكن ممكن أتعلم منها.",
    )
