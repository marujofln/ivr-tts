# CLAUDE.md

Outbound voice-message dialer for FreeSWITCH: a CSV of contacts is uploaded through a FastAPI app, a dialer
originates one call per row over ESL, and an ESL outbound socket server speaks a TTS message and hangs up.
See README.md for the architecture diagram and deployment.

## Commands

```bash
uv sync                                   # install deps (Python 3.12+)
uv run pytest                             # all tests
uv run pytest tests/test_dialer.py -k hangup   # single test
uv run uvicorn --app-dir ivr_tts app:app --reload   # API on :8000
uv run python ivr_tts/dialer.py           # dialer (needs FreeSWITCH + DB)
uv run python ivr_tts/tts_voice_message.py   # IVR socket server on :5000
uv run python ivr_tts/models.py           # DROP and recreate schema
```

uv is the only package manager: never use `pip install`, poetry or edit `requirements.txt` by hand.
Change dependencies with `uv add <pkg>` / `uv add --dev <pkg>` / `uv remove <pkg>` (updates `pyproject.toml`
and `uv.lock`; commit both), then regenerate `requirements.txt` with
`uv export --no-dev --no-emit-project --output-file requirements.txt`.
The Docker build uses `uv sync --frozen`, so a stale `uv.lock` breaks it.

## Code layout and conventions

- `ivr_tts/` is **not imported as a package**: each module is run as a script, so modules import each other as
  top-level names (`from settings import config`, `from models import Session`). Keep that style. `run.sh` and
  the tests put `ivr_tts/` on `sys.path` (`uvicorn --app-dir ivr_tts`, `tests/conftest.py`).
- Configuration: `ivr_tts/settings.py` (pydantic-settings), flat snake_case field names (`freeswitch_host`,
  `dialer_domain`...), loaded from env vars or `etc/.env`. `config = Settings()` runs **at import time**, so
  required fields must be set before importing any module. `database_url` is derived from `postgres_*` unless set.
  When adding a setting, also add it to `etc/.env.example` and the README table.
- Database: plain SQLAlchemy 2.0 in `models.py`. `Session` is a `scoped_session` keyed by greenlet
  (each IVR call runs in its own gevent greenlet). `Model.query` is available via `Session.query_property()`.
  Tables: `big_table_input` (contacts + call results) and `big_table_output` (IVR results).
- Concurrency is gevent/greenswitch, not asyncio (except the FastAPI app).
- `dialer.py` call flow: `start()` selects rows where `job_uuid IS NULL` → `FSInboundConnection.originate()` →
  `on_job_finished` (BACKGROUND_JOB) stores `job_status` → `on_channel_hangup` stores hangup cause/SIP status.
  The IVR finds the contact through the `data_id` channel variable set on originate.
- The spoken message lives in `TTSVoiceMessage.safe_run()`; company name and contact phone come from
  `ivr_company_name` / `ivr_contact_phone` settings. Never hardcode real company names or phone numbers.
- `ivr_tts/stuff/` and `ivr_tts/listener.py` are debug tools / legacy flows, not run in production and not tested.
- The Fief permission string `campaing:csv:write` is misspelled on purpose: it must match the permission
  configured on the Fief server.
- Formatter: black (see `.vscode`). Messages, logs and identifiers are English; TTS prompts are pt-BR.

## Tests

`tests/` uses pytest with an in-memory SQLite database (`DATABASE_URL=sqlite://` set in `conftest.py`) and
`unittest.mock` for ESL sessions/connections — no FreeSWITCH, PostgreSQL or Fief required. Use the `db`
fixture for a fresh schema. The API tests override the `app.csv_writer` auth dependency.

## Public repository hygiene

This repository is public. Never commit credentials, real contact lists, phone numbers, customer or company
names, internal hostnames/IPs, or captured FreeSWITCH events. Use `example.com` domains and fake data
(`csv/example.csv`). Real settings go in `etc/.env` (gitignored).
