# Motanafas backend

Start from `backend/` with Ollama running and `llama3.2:3b` available:

```bash
source .venv/bin/activate
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

`POST /api/reframe` uses Ollama by default. Configuration comes from environment
variables (export these before starting the server):

- `OLLAMA_API_URL`: defaults to `http://127.0.0.1:11434/api/generate`.
- `OLLAMA_MODEL`: defaults to `llama3.2:3b`.
- `MOTANAFAS_DEV_MOCK_AI=true`: explicitly enables the original fixed mock for
  local development only. Leave unset for real generation. It is never enabled
  automatically on an Ollama failure.

The generation code is adapted from `origin/Jood:ai_service.py`, with
non-clinical prompts, Pydantic validation, a 25-second HTTP timeout, and no
fabricated fallback. Unavailable Ollama, HTTP errors, timeouts, and invalid
responses return HTTP 503 with a generic Arabic `detail` message.

The backend safety service checks requests before generation. Its preliminary
phrase rules are not clinically validated; a non-match does not establish
safety. Jood's separate keyword checker is not used. The backend does not log
or persist user text, prompts, or generated responses. Ollama is a separate
process; its deployment and logging settings are managed independently.

`POST /api/panic` remains deterministic and does not use Ollama.

Run the tests without a running Ollama server (HTTP calls are mocked):

```bash
.venv/bin/python -m unittest discover -s tests -v
```
