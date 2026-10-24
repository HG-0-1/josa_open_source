import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from requests import Response

import database
from main import app
from models import AuthSession, JournalEntry
from services.auth_service import _LOGIN_FAILURES, hash_secret


async def _run_inline(function, *args, **kwargs):
    return function(*args, **kwargs)


class JournalApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="motanafas-journal-test-")
        database.configure_database(f"sqlite:///{self.temp_dir.name}/isolated.sqlite3")
        database.init_database()
        _LOGIN_FAILURES.clear()
        self.client_a = {"headers": {}}
        self.client_b = {"headers": {}}
        patcher = patch("routers.journal.to_thread", new=_run_inline)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        database.engine.dispose()
        self.temp_dir.cleanup()

    async def request(self, method, path, body=None, client=None, headers=None):
        client = client if client is not None else {"headers": {}}
        split = __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(path)
        request_headers = {
            b"content-type": b"application/json",
            b"origin": b"http://127.0.0.1:5173",
        }
        request_headers.update(client.get("headers", {}))
        request_headers.update(headers or {})
        payload = b"" if body is None else json.dumps(body, ensure_ascii=False).encode()
        messages = []

        async def receive():
            return {"type": "http.request", "body": payload, "more_body": False}

        async def send(message):
            messages.append(message)

        await app(
            {
                "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                "method": method, "scheme": "http", "path": split.path,
                "raw_path": split.path.encode(), "query_string": split.query.encode(),
                "root_path": "", "headers": list(request_headers.items()),
                "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
            },
            receive,
            send,
        )
        response_start = next(message for message in messages if message["type"] == "http.response.start")
        response_headers = dict(response_start["headers"])
        response_body = b"".join(
            message.get("body", b"")
            for message in messages if message["type"] == "http.response.body"
        )
        try:
            data = json.loads(response_body)
        except json.JSONDecodeError:
            data = None
        set_cookie = response_headers.get(b"set-cookie")
        if set_cookie:
            cookie_value = set_cookie.decode().split(";", 1)[0]
            if cookie_value.endswith("="):
                client["headers"].pop(b"cookie", None)
            else:
                client["headers"][b"cookie"] = cookie_value.encode()
        if isinstance(data, dict) and data.get("csrf_token"):
            client["headers"][b"x-csrf-token"] = data["csrf_token"].encode()
        return response_start["status"], data, response_headers

    async def register(self, client, email):
        status, data, headers = await self.request(
            "POST",
            "/api/auth/register",
            {"email": email, "password": "secure-demo-password"},
            client,
        )
        self.assertEqual(status, 201, data)
        self.assertTrue(data["authenticated"])
        self.assertIn(b"httponly", headers[b"set-cookie"].lower())
        self.assertIn(b"samesite=lax", headers[b"set-cookie"].lower())
        self.assertIn(b"path=/api", headers[b"set-cookie"].lower())
        return data["user"]

    async def test_health_endpoint(self):
        status, health, _ = await self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health, {"status": "ok", "service": "motanafas-backend"})

    async def add_entry(self, client, **overrides):
        payload = {
            "mood": "قلق",
            "intensity": 3,
            "trigger_category": "دراسة",
            "trigger_note": "امتحان قريب",
            "journal_text": "ملاحظة خاصة لا يجب أن تصل إلى Ollama.",
        }
        payload.update(overrides)
        return await self.request("POST", "/api/journal/entries", payload, client)

    async def test_register_login_logout_and_session_restore(self):
        await self.register(self.client_a, "A@example.com")
        status, me, _ = await self.request("GET", "/api/auth/me", client=self.client_a)
        self.assertEqual(status, 200)
        self.assertTrue(me["authenticated"])
        self.assertEqual(me["user"]["email"], "a@example.com")
        self.assertEqual(me["csrf_token"].encode(), self.client_a["headers"][b"x-csrf-token"])

        status, failed, _ = await self.request(
            "POST", "/api/auth/login",
            {"email": "a@example.com", "password": "wrong-password"}, self.client_b,
        )
        self.assertEqual(status, 401)
        self.assertNotIn("password", json.dumps(failed))

        status, logged_in, _ = await self.request(
            "POST", "/api/auth/login",
            {"email": "A@example.com", "password": "secure-demo-password"}, self.client_b,
        )
        self.assertEqual(status, 200)
        self.assertEqual(logged_in["user"]["email"], "a@example.com")
        status, _, _ = await self.request("POST", "/api/auth/logout", {}, self.client_b)
        self.assertEqual(status, 200)
        status, logged_out, _ = await self.request("GET", "/api/auth/me", client=self.client_b)
        self.assertEqual(status, 200)
        self.assertFalse(logged_out["authenticated"])

    async def test_session_expiration_rejects_protected_requests(self):
        await self.register(self.client_a, "expired@example.com")
        raw_cookie = self.client_a["headers"][b"cookie"].decode().split("=", 1)[1]
        db = database.SessionLocal()
        try:
            session = db.get(AuthSession, hash_secret(raw_cookie))
            self.assertIsNotNone(session)
            session.expires_at = 0
            db.commit()
        finally:
            db.close()

        status, auth, _ = await self.request("GET", "/api/auth/me", client=self.client_a)
        self.assertEqual(status, 200)
        self.assertFalse(auth["authenticated"])
        status, _, _ = await self.request("GET", "/api/journal/entries", client=self.client_a)
        self.assertEqual(status, 401)

    async def test_registration_validation_and_origin_protection(self):
        for payload in (
            {"email": "not-an-email", "password": "secure-demo-password"},
            {"email": "x@example.com", "password": "short"},
        ):
            status, response, _ = await self.request("POST", "/api/auth/register", payload, self.client_a)
            self.assertEqual(status, 422)
            self.assertNotIn("input", json.dumps(response))
        status, _, _ = await self.request(
            "POST", "/api/auth/register",
            {"email": "origin@example.com", "password": "secure-demo-password"},
            self.client_a,
            {b"origin": b"https://attacker.example"},
        )
        self.assertEqual(status, 403)

    async def test_protected_routes_and_csrf(self):
        status, _, _ = await self.request("GET", "/api/journal/entries")
        self.assertEqual(status, 401)
        status, _, _ = await self.request("POST", "/api/journal/entries", {
            "mood": "قلق", "intensity": 2, "trigger_category": "دراسة",
        })
        self.assertEqual(status, 401)

        await self.register(self.client_a, "csrf@example.com")
        status, _, _ = await self.request(
            "POST", "/api/journal/entries",
            {"mood": "قلق", "intensity": 2, "trigger_category": "دراسة"},
            self.client_a,
            {b"x-csrf-token": b"wrong-token"},
        )
        self.assertEqual(status, 403)

    async def test_entry_crud_and_strict_user_isolation(self):
        await self.register(self.client_a, "first@example.com")
        await self.register(self.client_b, "second@example.com")
        status, created, headers = await self.add_entry(self.client_a)
        self.assertEqual(status, 201)
        self.assertEqual(created["mood"], "قلق")
        self.assertEqual(created["intensity"], 3)
        self.assertEqual(created["trigger_category"], "دراسة")
        self.assertEqual(created["trigger_note"], "امتحان قريب")
        self.assertIn("ملاحظة خاصة", created["journal_text"])
        self.assertIn(b"no-store", headers[b"cache-control"])
        entry_id = created["id"]

        status, entries, _ = await self.request("GET", "/api/journal/entries", client=self.client_a)
        self.assertEqual(status, 200)
        self.assertEqual(len(entries["entries"]), 1)
        status, other_entries, _ = await self.request("GET", "/api/journal/entries", client=self.client_b)
        self.assertEqual(status, 200)
        self.assertEqual(other_entries["entries"], [])

        status, _, _ = await self.request("DELETE", f"/api/journal/entries/{entry_id}", {}, self.client_b)
        self.assertEqual(status, 404)
        status, _, _ = await self.request("DELETE", f"/api/journal/entries/{entry_id}", {}, self.client_a)
        self.assertEqual(status, 200)
        status, entries, _ = await self.request("GET", "/api/journal/entries", client=self.client_a)
        self.assertEqual(entries["entries"], [])

    async def test_entry_input_validation(self):
        await self.register(self.client_a, "validate@example.com")
        cases = (
            {"mood": "تشخيص", "intensity": 2, "trigger_category": "دراسة"},
            {"mood": "قلق", "intensity": 6, "trigger_category": "دراسة"},
            {"mood": "قلق", "intensity": 2, "trigger_category": "خارج القائمة"},
            {"mood": "قلق", "intensity": 2, "trigger_category": "دراسة", "journal_text": "x" * 5001},
        )
        for payload in cases:
            status, response, _ = await self.request("POST", "/api/journal/entries", payload, self.client_a)
            self.assertEqual(status, 422)
            self.assertNotIn("input", json.dumps(response))

    async def test_insights_use_saved_entries_and_report_associations_carefully(self):
        await self.register(self.client_a, "insights@example.com")
        status, initial, _ = await self.request("GET", "/api/journal/insights?days=7", client=self.client_a)
        self.assertEqual(status, 200)
        self.assertFalse(initial["sufficient_data"])
        self.assertEqual(initial["total_entries"], 0)
        self.assertEqual(initial["pattern_notes"], ["لسه بدنا تسجيلات أكثر حتى نلاحظ نمط واضح"])

        for mood, trigger in (
            ("قلق", "دراسة"), ("قلق", "دراسة"), ("حزن", "عائلة"),
            ("قلق", "نوم"), ("فرح", "شغل"),
        ):
            status, _, _ = await self.add_entry(
                self.client_a, mood=mood, trigger_category=trigger,
                trigger_note=None, journal_text=None,
            )
            self.assertEqual(status, 201)
        status, insights, _ = await self.request("GET", "/api/journal/insights?days=7", client=self.client_a)
        self.assertEqual(status, 200)
        self.assertTrue(insights["sufficient_data"])
        self.assertEqual(insights["total_entries"], 5)
        self.assertEqual(next(row["count"] for row in insights["mood_counts"] if row["label"] == "قلق"), 3)
        self.assertEqual(next(row["count"] for row in insights["trigger_counts"] if row["label"] == "دراسة"), 2)
        self.assertIn("لا يثبت سبب الشعور", " ".join(insights["pattern_notes"]))
        self.assertTrue(insights["intensity_trend"])

    async def test_insight_period_filtering_uses_saved_entry_dates(self):
        user = await self.register(self.client_a, "periods@example.com")
        for mood in ("قلق", "فرح"):
            status, _, _ = await self.add_entry(self.client_a, mood=mood, trigger_note=None, journal_text=None)
            self.assertEqual(status, 201)
        db = database.SessionLocal()
        try:
            entries = list(db.query(JournalEntry).filter_by(user_id=user["id"]).order_by(JournalEntry.id))
            now = datetime.now(timezone.utc)
            entries[0].created_at = now - timedelta(days=20)
            entries[1].created_at = now - timedelta(days=2)
            db.commit()
        finally:
            db.close()

        status, week, _ = await self.request(
            "GET", "/api/journal/insights?days=7", client=self.client_a,
        )
        self.assertEqual(status, 200)
        self.assertEqual(week["total_entries"], 1)
        status, month, _ = await self.request(
            "GET", "/api/journal/insights?days=30", client=self.client_a,
        )
        self.assertEqual(status, 200)
        self.assertEqual(month["total_entries"], 2)
        self.assertEqual(len(month["intensity_trend"]), 2)

    async def test_ai_reflection_requires_consent_and_sufficient_data_and_sends_aggregates_only(self):
        await self.register(self.client_a, "ai@example.com")
        status, _, _ = await self.request(
            "POST", "/api/journal/ai-insights", {"consent": True, "days": 7}, self.client_a,
        )
        self.assertEqual(status, 409)

        status, _, _ = await self.request(
            "POST", "/api/journal/ai-insights", {"consent": False, "days": 7}, self.client_a,
        )
        self.assertEqual(status, 422)

        for _ in range(5):
            status, _, _ = await self.add_entry(self.client_a)
            self.assertEqual(status, 201)

        ollama_response = Response()
        ollama_response.status_code = 200
        ollama_response._content = json.dumps({
            "response": json.dumps({
                "pattern": "سجلت القلق عدة مرات.",
                "evidence": "ظهر القلق في خمسة تسجيلات، وارتبطت فئتان بالدراسة.",
                "suggestion": "إذا ناسبك، جرّب ملاحظة ما يساعدك قبل الدراسة.",
            }, ensure_ascii=False),
        }, ensure_ascii=False).encode()
        with patch("services.journal_ai_service.requests.post", return_value=ollama_response) as ollama:
            status, insight, _ = await self.request(
                "POST", "/api/journal/ai-insights", {"consent": True, "days": 30}, self.client_a,
            )
        self.assertEqual(status, 200, insight)
        self.assertEqual(set(insight), {"pattern", "evidence", "suggestion"})
        submitted = json.loads(ollama.call_args.kwargs["json"]["prompt"])
        output_schema = ollama.call_args.kwargs["json"]["format"]
        self.assertEqual(set(output_schema["properties"]), {"pattern", "evidence", "suggestion"})
        self.assertEqual(set(output_schema["required"]), {"pattern", "evidence", "suggestion"})
        self.assertFalse(output_schema["additionalProperties"])
        self.assertEqual(submitted["entry_count"], 5)
        self.assertEqual(submitted["period_days"], 30)
        system_prompt = ollama.call_args.kwargs["json"]["system"]
        self.assertIn("جمل طبيعية دافئة", system_prompt)
        self.assertIn("لا تصف أي تزامن كسبب أو نتيجة", system_prompt)
        self.assertIn("جملة كاملة تذكر العدد والفئة والشعور", system_prompt)
        self.assertIn("لا تكتب رقماً وحده", system_prompt)
        self.assertIn("pattern وevidence وsuggestion", system_prompt)
        self.assertNotIn("journal_text", json.dumps(submitted))
        self.assertNotIn("trigger_note", json.dumps(submitted))
        self.assertNotIn("ملاحظة خاصة", json.dumps(submitted, ensure_ascii=False))

        # WSL may expose its Ollama service to the backend through a private VM IP.
        fenced = Response()
        fenced.status_code = 200
        fenced._content = json.dumps({
            "response": "```json\n" + json.dumps({
                "pattern": "سجلت القلق عدة مرات.",
                "evidence": "ظهر القلق في خمسة تسجيلات.",
                "suggestion": "إذا ناسبك، لاحظ ما يساعدك.",
            }, ensure_ascii=False) + "\n```",
        }, ensure_ascii=False).encode()
        with patch.dict("os.environ", {"OLLAMA_API_URL": "http://172.28.64.1:11434/api/generate"}):
            with patch("services.journal_ai_service.requests.post", return_value=fenced) as wsl_ollama:
                status, parsed, _ = await self.request(
                    "POST", "/api/journal/ai-insights", {"consent": True, "days": 30}, self.client_a,
                )
        self.assertEqual(status, 200, parsed)
        self.assertEqual(parsed["pattern"], "سجلت القلق عدة مرات.")
        self.assertEqual(wsl_ollama.call_args.args[0], "http://172.28.64.1:11434/api/generate")

        with patch("services.journal_ai_service.requests.post", side_effect=RuntimeError("private data")):
            status, _, _ = await self.request(
                "POST", "/api/journal/ai-insights", {"consent": True, "days": 30}, self.client_a,
            )
        self.assertEqual(status, 503)

        with patch.dict("os.environ", {"OLLAMA_API_URL": "https://example.com/api/generate"}):
            with patch("services.journal_ai_service.requests.post") as ollama, self.assertLogs(
                "services.journal_ai_service", level="WARNING"
            ) as failure_log:
                status, _, _ = await self.request(
                    "POST", "/api/journal/ai-insights", {"consent": True, "days": 30}, self.client_a,
                )
        self.assertEqual(status, 503)
        ollama.assert_not_called()
        self.assertIn("configuration (ValueError)", failure_log.output[0])
        self.assertNotIn("ملاحظة خاصة", failure_log.output[0])

    async def test_ai_invalid_language_or_malformed_output_fails_closed(self):
        await self.register(self.client_a, "bad-ai@example.com")
        for _ in range(5):
            await self.add_entry(self.client_a)
        responses = []
        for content in (
            "not json",
            json.dumps({
                "pattern": "Five records mention anxiety.",
                "evidence": "These records contain the mood anxiety.",
                "suggestion": "Optionally notice this trend.",
            }),
            json.dumps({
                "pattern": "تكرر تسجيل القلق.",
                "evidence": "٢",
                "suggestion": "إذا ناسبك، لاحظ ما يتكرر.",
            }, ensure_ascii=False),
        ):
            response = Response()
            response.status_code = 200
            response._content = json.dumps({"response": content}).encode()
            responses.append(response)
        for body in responses:
            with patch("services.journal_ai_service.requests.post", return_value=body):
                status, data, _ = await self.request(
                    "POST", "/api/journal/ai-insights", {"consent": True, "days": 30}, self.client_a,
                )
                self.assertEqual(status, 503)
                self.assertNotIn("not json", json.dumps(data))

    async def test_ai_schema_retry_corrects_missing_fields_and_logs_safe_paths(self):
        await self.register(self.client_a, "schema-retry@example.com")
        for _ in range(5):
            await self.add_entry(self.client_a)

        def ollama_response(content):
            response = Response()
            response.status_code = 200
            response._content = json.dumps({"response": content}, ensure_ascii=False).encode()
            return response

        malformed = json.dumps({
            "pattern": "نص مولد خاص للاختبار.",
            "suggestion": "اقتراح اختياري.",
            "unexpected": "حقل زائد.",
        }, ensure_ascii=False)
        valid = json.dumps({
            "pattern": "تكرر تسجيل القلق.",
            "evidence": "ظهر القلق في خمسة تسجيلات.",
            "suggestion": "إذا ناسبك، لاحظ الفئات التي تتكرر.",
        }, ensure_ascii=False)
        with patch(
            "services.journal_ai_service.requests.post",
            side_effect=[ollama_response(malformed), ollama_response(valid)],
        ) as ollama:
            status, result, _ = await self.request(
                "POST", "/api/journal/ai-insights", {"consent": True, "days": 30}, self.client_a,
            )
        self.assertEqual(status, 200, result)
        self.assertEqual(result["evidence"], "ظهر القلق في خمسة تسجيلات.")
        self.assertEqual(ollama.call_count, 2)
        retry_payload = ollama.call_args_list[1].kwargs["json"]
        self.assertIn("أعد التنسيق فقط", retry_payload["prompt"])
        retry_data = json.loads(retry_payload["prompt"])
        self.assertEqual(retry_data["aggregates"]["entry_count"], 5)
        self.assertNotIn("ملاحظة خاصة", json.dumps(retry_data, ensure_ascii=False))

        with patch(
            "services.journal_ai_service.requests.post",
            side_effect=[ollama_response(malformed), ollama_response(malformed)],
        ), self.assertLogs("services.journal_ai_service", level="WARNING") as failure_log:
            status, _, _ = await self.request(
                "POST", "/api/journal/ai-insights", {"consent": True, "days": 30}, self.client_a,
            )
        self.assertEqual(status, 503)
        self.assertIn("fields=unexpected,evidence", failure_log.output[-1])
        self.assertNotIn("نص مولد خاص للاختبار", failure_log.output[-1])
        self.assertNotIn("ملاحظة خاصة", failure_log.output[-1])

    async def test_account_deletion_removes_entries_and_invalidates_session(self):
        user = await self.register(self.client_a, "delete@example.com")
        status, entry, _ = await self.add_entry(self.client_a)
        self.assertEqual(status, 201)
        status, _, _ = await self.request(
            "DELETE", "/api/auth/account", {"password": "wrong-password"}, self.client_a,
        )
        self.assertEqual(status, 403)
        status, _, _ = await self.request(
            "DELETE", "/api/auth/account", {"password": "secure-demo-password"}, self.client_a,
        )
        self.assertEqual(status, 200)
        status, me, _ = await self.request("GET", "/api/auth/me", client=self.client_a)
        self.assertEqual(status, 200)
        self.assertFalse(me["authenticated"])
        status, _, _ = await self.request("GET", "/api/journal/entries")
        self.assertEqual(status, 401)
        db = database.SessionLocal()
        try:
            self.assertEqual(db.query(JournalEntry).filter_by(user_id=user["id"]).count(), 0)
            self.assertEqual(db.query(AuthSession).filter_by(user_id=user["id"]).count(), 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
