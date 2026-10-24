from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import logging
import unittest
from unittest.mock import patch
from urllib.error import URLError

from main import app


class PanicTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Every grounding test runs with Ollama unavailable, without contacting it.
        http_patch = patch(
            "services.ai_service.urlopen", side_effect=URLError(ConnectionRefusedError())
        )
        self.http = http_patch.start()
        self.addCleanup(http_patch.stop)

    async def asyncTearDown(self):
        self.http.assert_not_called()

    async def post(self, payload: object) -> tuple[int, dict]:
        """Call the actual ASGI endpoint without extra test dependencies."""
        messages = []

        async def receive():
            return {
                "type": "http.request",
                "body": json.dumps(payload).encode(),
                "more_body": False,
            }

        async def send(message):
            messages.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/panic",
                "raw_path": b"/api/panic",
                "query_string": b"",
                "root_path": "",
                "headers": [(b"content-type", b"application/json")],
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
            },
            receive,
            send,
        )
        status = next(m["status"] for m in messages if m["type"] == "http.response.start")
        body = b"".join(
            m.get("body", b"") for m in messages if m["type"] == "http.response.body"
        )
        return status, json.loads(body)

    async def test_all_steps_without_ai(self):
        expected = {
            1: "أربعة أشياء بتقدر تلمسها",
            2: "ثلاثة أصوات",
            3: "ريحتين إذا متاحين",
            4: "طعم واحد",
            5: "خلصت خطوات التمرين",
        }
        with patch("services.ai_service.reframe", side_effect=RuntimeError) as ai:
            for step, phrase in expected.items():
                with self.subTest(step=step):
                    status, response = await self.post({"step": step, "text": "شايف الشباك"})
                    self.assertEqual(status, 200)
                    self.assertIn(phrase, response["reply"])
                    self.assertIs(response["emergency"], False)
                    self.assertEqual(response["completed"], step == 5)
                    self.assertEqual(set(response), {"reply", "emergency", "completed"})
                    for claim in ("إنت بأمان", "أنت بأمان", "نبضك بدأ يهدأ",
                                  "نوبة هلع مؤكدة", "you are safe", "pulse is slowing"):
                        self.assertNotIn(claim, response["reply"])
            ai.assert_not_called()

    async def test_invalid_steps(self):
        for step in (0, 6, -1, "1", 1.0, True, None):
            with self.subTest(step=step):
                status, _ = await self.post({"step": step})
                self.assertEqual(status, 422)
        status, _ = await self.post({})
        self.assertEqual(status, 422)

    async def test_optional_and_empty_text(self):
        for payload in ({"step": 1}, {"step": 1, "text": ""},
                        {"step": 1, "text": "   "}, {"step": 1, "text": None}):
            with self.subTest(payload=payload):
                status, response = await self.post(payload)
                self.assertEqual(status, 200)
                self.assertIs(response["emergency"], False)

    async def test_text_validation(self):
        status, _ = await self.post({"step": 1, "text": "x" * 1000})
        self.assertEqual(status, 200)
        for text in ("x" * 1001, 123, []):
            status, response = await self.post({"step": 1, "text": text})
            self.assertEqual(status, 422)
            self.assertTrue(all("input" not in error for error in response["detail"]))

    async def test_danger_overrides_every_step_and_stop(self):
        with patch("services.grounding_service.next_guidance") as grounding, \
                patch("services.ai_service.reframe") as ai:
            for step in range(1, 6):
                for action in ("continue", "skip", "stop"):
                    status, response = await self.post({
                        "step": step, "text": "أنا ناوي أؤذي نفسي الآن", "action": action
                    })
                    self.assertEqual(status, 200)
                    self.assertEqual(response, {
                        "reply": "إذا كنت في خطر مباشر، اطلب مساعدة بشرية أو اتصل بالطوارئ.",
                        "emergency": True, "completed": False,
                    })
            grounding.assert_not_called()
            ai.assert_not_called()

    async def test_severe_symptoms_override_exercise(self):
        symptoms = (
            "عندي ألم شديد في الصدر", "عندي ألم شديد بصدري",
            "أشعر بألم في الصدر شديد", "عندي ضيق شديد في التنفس",
            "عندي صعوبة شديدة بالتنفس", "عندي ضيق تنفس شديد",
            "مش قادر أتنفس", "لا أستطيع التنفس",
            "I have severe chest pain", "I can't breathe",
            "I have severe difficulty breathing",
        )
        with patch("services.grounding_service.next_guidance") as grounding, \
                patch("services.ai_service.reframe") as ai:
            for index, text in enumerate(symptoms):
                for step in range(1, 6):
                    with self.subTest(case=index, step=step):
                        status, response = await self.post({"step": step, "text": text})
                        self.assertEqual(status, 200)
                        self.assertEqual(response, {
                            "reply": (
                                "الألم الشديد بالصدر أو الصعوبة الشديدة بالتنفس يحتاجوا تقييم طبي عاجل. "
                                "أوقف التمرين واتصل بالطوارئ المحلية أو اطلب مساعدة طبية فوراً. "
                                "ما بنقدر نفترض إن السبب قلق."
                            ),
                            "emergency": True, "completed": False,
                        })
            grounding.assert_not_called()
            ai.assert_not_called()

    async def test_negated_and_example_quoted_statements(self):
        statements = (
            "أنا مش ناوي أؤذي نفسي الآن",
            'قرأت مثالاً: «أنا حزين، أنا ناوي أؤذي نفسي الآن.»',
            "ما عندي ألم شديد في الصدر", "لا أعاني من صعوبة شديدة في التنفس",
            'قرأت عن «ألم شديد في الصدر»',
            'An example says "I cannot breathe".',
        )
        for index, text in enumerate(statements):
            with self.subTest(case=index):
                status, response = await self.post({"step": 1, "text": text})
                self.assertEqual(status, 200)
                self.assertIs(response["emergency"], False)
                self.assertIn("أربعة أشياء", response["reply"])

    async def test_sensitive_input_is_not_echoed_or_logged(self):
        statements = (
            "هذه فكرة شخصية خاصة للاختبار",
            "أنا ناوي أؤذي نفسي الآن", "عندي ألم شديد في الصدر",
        )
        logs, stdout, stderr = StringIO(), StringIO(), StringIO()
        handler = logging.StreamHandler(logs)
        logger = logging.getLogger()
        original_level = logger.level
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                for text in statements:
                    status, response = await self.post({"step": 1, "text": text})
                    self.assertEqual(status, 200)
                    self.assertNotIn(text, json.dumps(response, ensure_ascii=False))
                with patch("services.safety_service.is_clearly_urgent",
                           side_effect=RuntimeError(statements[0])):
                    status, response = await self.post({"step": 1, "text": statements[0]})
                    self.assertEqual(status, 500)
                    self.assertNotIn(statements[0], json.dumps(response, ensure_ascii=False))
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)
        observed = logs.getvalue() + stdout.getvalue() + stderr.getvalue()
        for text in statements:
            self.assertNotIn(text, observed)
            self.assertNotIn(json.dumps(text)[1:-1], observed)

    async def test_ordinary_distress(self):
        status, response = await self.post({"step": 2, "text": "حاسس إني فاشل وزعلان"})
        self.assertEqual(status, 200)
        self.assertIs(response["emergency"], False)

    async def test_skip_and_stop(self):
        status, response = await self.post({"step": 1, "action": "skip"})
        self.assertEqual(status, 200)
        self.assertIn("أربعة أشياء", response["reply"])
        for payload in ({"step": 2, "action": "stop"}, {"step": 1, "text": "توقف"}):
            status, response = await self.post(payload)
            self.assertEqual(status, 200)
            self.assertIs(response["completed"], True)
            self.assertIs(response["emergency"], False)
            self.assertIn("وقفنا التمرين", response["reply"])

    async def test_service_failure_is_generic(self):
        private_text = "هذه عبارة خاصة للاختبار"
        for target in ("services.grounding_service.next_guidance",
                       "services.safety_service.is_clearly_urgent",
                       "services.safety_service.has_urgent_physical_symptoms"):
            with self.subTest(service=target), patch(target, side_effect=RuntimeError(private_text)):
                status, response = await self.post({"step": 1, "text": private_text})
                self.assertEqual(status, 500)
                self.assertEqual(response, {"detail": "تعذر معالجة الطلب. يرجى المحاولة لاحقاً."})
                self.assertNotIn(private_text, json.dumps(response, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
