"""Optional local-only reflection over journal aggregates."""

import json
import ipaddress
import logging
import math
import os
import re
import time
from urllib.parse import urlparse

import requests
from pydantic import ValidationError
from schemas.journal import AiInsightsOut
from services.ai_service import MODEL_NAME, OLLAMA_API_URL, clean_json_response
from services.journal_service import aggregate_for_ai


class JournalAIUnavailable(Exception):
    pass


def _is_local_ollama_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "http" or not parsed.hostname:
        return False
    if parsed.hostname.lower() == "localhost":
        return True
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    local_networks = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("fc00::/7"),
    )
    return any(address in network for network in local_networks if address.version == network.version)


def _output_language_error_paths(result: AiInsightsOut) -> tuple[str, ...]:
    arabic_letter = re.compile(r"[\u0621-\u064A\u066E-\u06D3\u06FA-\u06FC]")
    latin_letter = re.compile(r"[A-Za-z]")
    errors = []
    for field, value in result.model_dump().items():
        if latin_letter.search(value) or not arabic_letter.search(value):
            errors.append(field)
    if re.fullmatch(r"[\d٠-٩۰-۹\s.,،؛;:]+", result.evidence):
        errors.append("evidence")
    return tuple(dict.fromkeys(errors))


def reflect(entries: list, period_days: int = 30) -> AiInsightsOut:
    aggregates = aggregate_for_ai(entries)
    aggregates["period_days"] = period_days
    system_prompt = (
        "أنت مساعد تأمل ذاتي غير سريري. اكتب بالعربية الأردنية البيضاء، بجمل طبيعية دافئة وموجزة. "
        "اعتمد حصراً على الأعداد والفئات المرفقة؛ لا تخترع أحداثاً أو عادات أو حقائق، ولا تشخّص. "
        "لا تصف أي تزامن كسبب أو نتيجة. إذا لم يتكرر اقتران شعور وفئة، قل بلطف إن التسجيلات لا تُظهر نمطاً واضحاً. "
        "pattern يصف الاقتران المتكرر بحذر كاحتمال، خصوصاً مع قلة التسجيلات. evidence جملة كاملة تذكر العدد والفئة والشعور "
        "كما وردت في البيانات والفترة المحددة؛ لا تكتب رقماً وحده ولا تضف أعداداً غير موجودة. "
        "suggestion جملة اختيارية داعمة وعامة، بلا افتراض نشاط أو روتين لدى المستخدم. "
        "مثال أسلوبي فقط عند تكرر الفرح مع العائلة مرتين: "
        "pattern: لاحظنا إنك سجلت الفرح مع فئة العائلة مرتين؛ ممكن تكون لحظات مريحة إلك. "
        "evidence: بحسب يومياتك، ظهر الفرح مع فئة العائلة مرتين خلال الفترة المحددة. "
        "suggestion: إذا بناسبك، جرّب وقتاً بسيطاً لنشاط بتحبه مع العائلة، ولاحظ شعورك بعده. "
        "غيّر الصياغة وفق الأعداد ولا تنسخ المثال إن لم تدعمه البيانات. "
        "أعد JSON صالحاً فقط بالمفاتيح الثلاثة بالضبط: pattern وevidence وsuggestion. "
        "كل قيمة نص عربي غير فارغ لا يتجاوز 500 حرف، ومن دون مفاتيح إضافية أو نص خارج JSON."
    )
    schema = AiInsightsOut.model_json_schema()
    base_payload = {
        "model": os.getenv("OLLAMA_MODEL", MODEL_NAME),
        "system": system_prompt,
        "prompt": json.dumps(aggregates, ensure_ascii=False),
        "stream": False,
        "format": schema,
        "options": {"temperature": 0.1, "num_predict": 180},
    }
    stage = "configuration"
    validation_paths: tuple[str, ...] = ()
    try:
        ollama_url = os.getenv("OLLAMA_API_URL", OLLAMA_API_URL)
        if not _is_local_ollama_url(ollama_url):
            raise ValueError("Journal reflection requires a local Ollama endpoint")
        timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Invalid timeout")
        deadline = time.monotonic() + timeout
        for attempt in range(2):
            payload = dict(base_payload)
            if attempt:
                payload["prompt"] = json.dumps({
                    "aggregates": aggregates,
                    "formatting_instruction": (
                        "أعد التنسيق فقط. أعد JSON صالحاً يحتوي pattern وevidence وsuggestion فقط. "
                        "كل قيمة نص عربي غير فارغ لا يتجاوز 500 حرف. لا تخترع معلومات؛ "
                        "استخدم الأعداد والفئات والفترة المرفقة حصراً، واكتب evidence جملة كاملة لا رقماً منفرداً. "
                        "لا تصف التزامن كسببية ولا تخترع أي وقائع."
                    ),
                }, ensure_ascii=False)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Ollama request deadline exceeded")
            stage = "request"
            response = requests.post(ollama_url, json=payload, timeout=remaining)
            response.raise_for_status()
            stage = "response parsing"
            if len(response.content) > 32768:
                raise ValueError("Oversized response")
            envelope = response.json()
            if not isinstance(envelope, dict) or not isinstance(envelope.get("response"), str):
                raise ValueError("Invalid Ollama response")
            try:
                result = AiInsightsOut.model_validate_json(clean_json_response(envelope["response"]))
            except ValidationError as exc:
                validation_paths = _validation_paths(exc)
                if attempt == 0:
                    continue
                raise
            stage = "language validation"
            language_paths = _output_language_error_paths(result)
            if language_paths:
                if attempt == 0:
                    validation_paths = language_paths
                    continue
                raise ValueError("Unexpected non-Arabic reflection")
            return result
        raise ValueError("Ollama response failed validation")
    except Exception as exc:
        # Record only the failure stage, exception class and schema paths.
        path_suffix = f" fields={','.join(validation_paths)}" if validation_paths else ""
        logging.getLogger(__name__).warning(
            "Journal reflection unavailable during %s (%s)%s",
            stage, type(exc).__name__, path_suffix,
        )
        raise JournalAIUnavailable("Journal reflection unavailable") from None


def _validation_paths(error: ValidationError) -> tuple[str, ...]:
    """Extract schema locations only; never retain Pydantic input or messages."""
    paths = []
    for item in error.errors():
        location = ".".join(str(part) for part in item.get("loc", ())) or "root"
        if location not in paths:
            paths.append(location)
    return tuple(paths[:10])
