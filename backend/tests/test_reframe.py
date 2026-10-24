import json
import unittest
from unittest.mock import patch

from main import app


class ReframeTests(unittest.IsolatedAsyncioTestCase):
    async def post(self, payload: object) -> tuple[int, dict]:
        """Exercise the ASGI app without adding an HTTP testing dependency."""
        body = json.dumps(payload).encode()
        messages = []

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/reframe",
                "raw_path": b"/api/reframe",
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
        response = b"".join(
            m.get("body", b"") for m in messages if m["type"] == "http.response.body"
        )
        return status, json.loads(response)

    async def test_normal_input(self):
        status, response = await self.post(
            {"text": "حاسس إني فاشل لأن مقابلة العمل ما زبطت"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(response, {
            "emergency": False,
            "distortion": "نمط تفكير محتمل: التعميم الزائد",
            "reality_check": "تجربة واحدة لا تحدد كل قدراتك.",
            "reframed_thought": "المقابلة ما نجحت، لكن ممكن أتعلم منها.",
        })

    async def test_invalid_input(self):
        for payload in ({}, {"text": ""}, {"text": "   "}, {"text": "ab"},
                        {"text": "x" * 2001}, {"text": None}, {"text": 123},
                        {"text": []}, None):
            with self.subTest(payload_type=type(payload).__name__):
                status, response = await self.post(payload)
                self.assertEqual(status, 422)
                self.assertIn("detail", response)
                for error in response["detail"]:
                    self.assertNotIn("input", error)

    async def test_length_boundaries(self):
        for length in (3, 2000):
            with self.subTest(length=length):
                status, _ = await self.post({"text": "x" * length})
                self.assertEqual(status, 200)

    async def test_urgent_input_bypasses_ai(self):
        for text in ("أنا سأنتحر الآن", "رح أنتحر الليلة",
                     "أريد أن أقتل نفسي الآن", "أنا على وشك الانتحار",
                     "أخذت جرعة زائدة من الدواء الآن",
                     "I am going to kill myself right now."):
            with self.subTest(text=text), patch("services.ai_service.reframe") as ai:
                status, response = await self.post({"text": text})
                self.assertEqual(status, 200)
                self.assertEqual(response, {
                    "emergency": True,
                    "message": "إذا كنت في خطر مباشر، اطلب مساعدة بشرية أو اتصل بالطوارئ.",
                    "helpline": "911",
                })
                ai.assert_not_called()

    async def test_immediate_self_harm_intent_bypasses_ai(self):
        statements = (
            "أنا ناوي أؤذي نفسي الآن",
            "انا ناوي اوذي نفسي الان",
            "أنا ناوي أأذي نفسي الآن",
            "أنا ناوي آذي نفسي هلأ",
            "أنا ناوية أؤذي نفسي الآن",
            "أنا ناويه اذي حالي هلق",
            "أَنَا نَاوِي أُؤْذِي نَفْسِي الآن",
            "أنا ناوي أؤذي نفسي الآن",  # Decomposed alef with maddah.
            "أنا   ناوي أؤذي نفسي الآن!",
            "أنا بدي أؤذي نفسي هلا",
            "رح أؤذي حالي الآن",
            "سأؤذي نفسي الآن",
            "أنا حزين، أنا ناوي أؤذي نفسي الآن",
        )
        for index, text in enumerate(statements):
            with self.subTest(case=index), patch(
                "services.ai_service.reframe", side_effect=RuntimeError("AI must be bypassed")
            ) as ai:
                status, response = await self.post({"text": text})
                self.assertEqual(status, 200)
                self.assertEqual(response, {
                    "emergency": True,
                    "message": "إذا كنت في خطر مباشر، اطلب مساعدة بشرية أو اتصل بالطوارئ.",
                    "helpline": "911",
                })
                ai.assert_not_called()

    async def test_self_harm_negation_and_ordinary_distress(self):
        statements = (
            "أنا مش ناوي أؤذي نفسي الآن",
            "أنا مو ناوي أؤذي نفسي الآن",
            "أنا لا أريد أن أؤذي نفسي",
            "أنا لن أؤذي نفسي الآن",
            "أنا ناوي ما أؤذي نفسي",
            "هل أنا ناوي أؤذي نفسي الآن؟",
            "كنت ناوي أؤذي نفسي زمان لكن الآن لا أريد ذلك",
            "أنا حزين ومقهور من الشغل",
            "حاسس إني فاشل لأن مقابلة العمل ما زبطت",
            "أنا محبط وناوي أغير شغلي الآن",
        )
        for index, text in enumerate(statements):
            with self.subTest(case=index):
                status, response = await self.post({"text": text})
                self.assertEqual(status, 200)
                self.assertIs(response["emergency"], False)

    async def test_empty_input_bypasses_services(self):
        for text in ("", "   ", "\n\t"):
            with self.subTest(length=len(text)), \
                    patch("services.safety_service.is_clearly_urgent") as safety, \
                    patch("services.ai_service.reframe") as ai:
                status, _ = await self.post({"text": text})
                self.assertEqual(status, 422)
                safety.assert_not_called()
                ai.assert_not_called()

    async def test_negative_thoughts_and_negation_are_not_emergencies(self):
        for text in ("حاسس إني فاشل", "أنا حزين ومش قادر أركز",
                     "لا أريد أن أنتحر", "أنا لن أنتحر الآن",
                     "I will not kill myself", "هل سأنتحر الآن؟"):
            with self.subTest(text=text):
                status, response = await self.post({"text": text})
                self.assertEqual(status, 200)
                self.assertIs(response["emergency"], False)

    async def test_unexpected_ai_failure(self):
        private_text = "هذه فكرة شخصية خاصة"
        with patch("services.ai_service.reframe", side_effect=RuntimeError(private_text)):
            status, response = await self.post({"text": private_text})
        self.assertEqual(status, 500)
        self.assertEqual(response, {"detail": "تعذر معالجة الطلب. يرجى المحاولة لاحقاً."})
        self.assertNotIn(private_text, json.dumps(response, ensure_ascii=False))

    async def test_unexpected_safety_failure_does_not_call_ai(self):
        with patch("services.safety_service.is_clearly_urgent", side_effect=RuntimeError), \
                patch("services.ai_service.reframe") as ai:
            status, _ = await self.post({"text": "أنا سأنتحر الآن"})
        self.assertEqual(status, 500)
        ai.assert_not_called()


if __name__ == "__main__":
    unittest.main()
