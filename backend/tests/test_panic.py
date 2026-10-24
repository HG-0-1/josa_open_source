import json
import unittest
from unittest.mock import patch

from main import app


class PanicTests(unittest.IsolatedAsyncioTestCase):
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
        with patch("services.grounding_service.next_guidance") as grounding:
            for step in range(1, 6):
                status, response = await self.post({
                    "step": step, "text": "أنا ناوي أؤذي نفسي الآن", "action": "stop"
                })
                self.assertEqual(status, 200)
                self.assertIs(response["emergency"], True)
                self.assertIs(response["completed"], False)
                self.assertIn("مساعدة بشرية", response["reply"])
            grounding.assert_not_called()

    async def test_severe_symptoms_override_exercise(self):
        symptoms = (
            "عندي ألم شديد في الصدر", "عندي ألم شديد بصدري",
            "أشعر بألم في الصدر شديد", "عندي ضيق شديد في التنفس",
            "عندي صعوبة شديدة بالتنفس", "عندي ضيق تنفس شديد",
            "مش قادر أتنفس", "لا أستطيع التنفس",
            "I have severe chest pain", "I can't breathe",
            "I have severe difficulty breathing",
        )
        with patch("services.grounding_service.next_guidance") as grounding:
            for index, text in enumerate(symptoms):
                with self.subTest(case=index):
                    status, response = await self.post({"step": 1, "text": text})
                    self.assertEqual(status, 200)
                    self.assertIs(response["emergency"], True)
                    self.assertIs(response["completed"], False)
                    self.assertIn("تقييم طبي عاجل", response["reply"])
                    self.assertIn("الطوارئ المحلية", response["reply"])
            grounding.assert_not_called()

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
