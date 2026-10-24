"""Fixed, optional grounding prompts, without AI, diagnosis, or stored state.

The frontend starts with noticing five things you can see (step 1). Each
submitted step returns the next prompt. Empty answers and skipping are fine.
"""

from schemas.panic import PanicResponse


_NEXT_STEP = {
    1: "خذ وقتك. إذا بتحب، انتقل لملاحظة أربعة أشياء بتقدر تلمسها.",
    2: "إذا بتحب تكمل، لاحظ ثلاثة أصوات بتقدر تسمعها حولك.",
    3: "على مهلك. لاحظ ريحتين إذا متاحين، أو تخطّى هالخطوة.",
    4: "إذا بتحب، لاحظ طعم واحد، أو ببساطة خذ لحظة راحة.",
}
_CHOICE = " ممكن تتخطّى أي خطوة أو توقف التمرين بأي وقت."
_STOP_COMMANDS = {"stop", "توقف", "وقف", "بدي أوقف", "بدي اوقف"}


def next_guidance(step: int, text: str = "", action: str = "continue") -> PanicResponse:
    if action == "stop" or text.strip().lower() in _STOP_COMMANDS:
        return PanicResponse(
            reply="وقفنا التمرين. خذ وقتك، ومش مطلوب منك تكمل.", completed=True
        )
    if step == 5:
        return PanicResponse(
            reply="خلصت خطوات التمرين. خذ وقتك للراحة، ومش مطلوب منك تحسّ بشعور معيّن.",
            completed=True,
        )
    return PanicResponse(reply=_NEXT_STEP[step] + _CHOICE)
