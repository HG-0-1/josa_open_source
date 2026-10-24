"""Preliminary routing for a few explicit urgent statements.

These narrow phrase rules are not a clinically validated risk-assessment
system. They can miss urgent content; a non-match does not establish that a
person is safe. They do not infer risk from sadness or frustration alone.
"""

import re
import unicodedata


_URGENT_STATEMENTS = (
    # Explicit first-person self-harm intent, including common spelling and
    # dialect variants. Keep intent and self-directed action together.
    r"(?:انا )?(?:(?:ناوي|ناويه)(?: ان)?|اريد ان|بدي|رح|راح|سوف) "
    r"(?:اوذي|ااذي|اذي) (?:نفسي|حالي)"
    r"(?: الان| هلا| هلق| دلوقتي| الحين| الليله| اليوم)?",
    r"(?:انا )?س(?:اوذي|ااذي|اذي) (?:نفسي|حالي)"
    r"(?: الان| هلا| هلق| دلوقتي| الحين| الليله| اليوم)?",
    r"(?:انا )?(?:سانتحر|رح انتحر|راح انتحر|ساقتل نفسي|رح اقتل نفسي)"
    r"(?: الان| الليله| اليوم)?",
    r"(?:انا )?(?:اريد ان انتحر|اريد ان اقتل نفسي|بدي انتحر|بدي اقتل حالي)"
    r"(?: الان| الليله| اليوم)?",
    r"(?:انا )?علي وشك الانتحار",
    r"(?:انا )?(?:احاول الان ان انتحر|احاول الان قتل نفسي)",
    r"(?:انا )?(?:اخذت|تناولت) جرعه زائده من (?:الدواء|الحبوب)(?: الان)?",
    r"i (?:am going to|will) (?:kill myself|end my life)(?: right now| tonight| now)?",
    r"i (?:just took|have just taken) an overdose",
)


def _normalize(text: str) -> str:
    # Compose decomposed hamza/maddah before removing Arabic vowel marks.
    normalized = unicodedata.normalize("NFKC", text).lower()
    normalized = re.sub(r"[\u064b-\u065f\u0670ـ]", "", normalized)
    normalized = normalized.translate(str.maketrans("أإآىةؤ", "ااايهو"))
    return " ".join(normalized.split())


def is_clearly_urgent(text: str) -> bool:
    # Match complete clauses to avoid treating negation, questions, or ordinary
    # negative thoughts containing similar words as explicit urgent statements.
    clauses = re.split(r"[.!?؟،,;؛\n]+", text)
    return any(
        re.fullmatch(pattern, _normalize(clause)) is not None
        for clause in clauses
        for pattern in _URGENT_STATEMENTS
    )


_URGENT_PHYSICAL_SYMPTOMS = (
    r"(?:الم|وجع) (?:شديد|قوي|حاد) (?:جدا )?(?:(?:في|ب) )?(?:الصدر|صدري|بصدري|بالصدر)",
    r"(?:الم|وجع) (?:في |ب)?(?:الصدر|صدري|بصدري|بالصدر) (?:شديد|قوي|حاد)",
    r"(?:ضيق|صعوبه) (?:شديد|شديده) (?:جدا )?(?:في |ب)?(?:التنفس|تنفسي)",
    r"(?:ضيق|صعوبه) (?:في )?(?:التنفس|تنفس) (?:شديد|شديده)",
    r"(?:مش قادر|مو قادر|مش قادره|ما بقدر|لا استطيع) (?:ان )?(?:اتنفس|التنفس)",
    r"severe chest pain",
    r"(?:severe|serious) (?:difficulty breathing|breathing difficulty)",
    r"(?:can't|cannot|can’t) breathe",
)


def has_urgent_physical_symptoms(text: str) -> bool:
    """Conservatively route symptom mentions; not a diagnosis or clinical triage.

    Phrase detection can miss symptoms or flag quoted/negated mentions. It must
    never be used to conclude that symptoms are harmless or caused by panic.
    Guidance follows https://www.nhs.uk/symptoms/shortness-of-breath/.
    """
    normalized = _normalize(text)
    return any(re.search(pattern, normalized) for pattern in _URGENT_PHYSICAL_SYMPTOMS)
