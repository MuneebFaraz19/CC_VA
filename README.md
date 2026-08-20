# Voice AI Agent — Patient Registration System

A voice-based AI agent accessible via a real phone number that collects U.S. patient demographic information through natural conversation, persists it to a database, and exposes it through a REST API with a web dashboard.

## Architecture

```
Phone Call (Caller)
    ↕
Vapi (Telephony + STT + TTS)
    ↕  webhook
FastAPI Backend (Python)
    ├── /vapi/webhook     ← voice agent tool calls
    ├── /patients         ← REST CRUD API
    ├── /calls            ← call transcripts/logs
    └── / (dashboard)     ← web UI
    ↕
PostgreSQL Database (Render Postgres — persistent across restarts)
```

### Tech Stack & Justification

| Layer | Technology | Why |
|-------|-----------|-----|
| **Telephony + Voice** | Vapi | Abstracts STT/TTS/telephony — fastest path to a working voice agent. Handles phone number provisioning, speech-to-text (Deepgram), text-to-speech (ElevenLabs), and orchestrates the LLM. |
| **LLM** | Groq (Llama 3.3 70B) | Fast inference, good conversational quality, free tier available. Used as Vapi's model provider. |
| **Backend** | Python FastAPI | Async, fast, excellent validation via Pydantic, automatic OpenAPI docs. |
| **Database** | PostgreSQL (Render Postgres) | Persistent across restarts. SQLite used for local dev (auto-detected from `DATABASE_URL`). |
| **Hosting** | Render | Simple cloud deployment with managed PostgreSQL. |

## Quick Start

### Prerequisites
- Python 3.11+
- A Groq API key (free at [console.groq.com](https://console.groq.com))
- A Vapi API key (free at [vapi.ai](https://vapi.ai))

### Local Setup

```bash
# 1. Clone and install
cd voice-ai-patient-registration
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — add your GROQ_API_KEY and VAPI_API_KEY

# 3. (Optional) Seed demo data
python -m app.seed

# 4. Start the server
python -m uvicorn app.api:app --reload --port 8000
```

The API is now running at `http://localhost:8000`
- Dashboard: `http://localhost:8000/`
- API docs (Swagger): `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### Provisioning the Phone Number

```bash
# 5. Set PUBLIC_BASE_URL in .env to your public URL (use ngrok for local dev)
#    e.g. PUBLIC_BASE_URL=https://abc123.ngrok.io
ngrok http 8000  # in a separate terminal

# 6. Create the Vapi assistant and buy a phone number
python -m app.setup_vapi
```

This will print the phone number to call and the IDs to add to your `.env`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | No | Database URL. SQLite for local dev (`sqlite:///./patients.db`), PostgreSQL for production (`postgresql://...`) |
| `GROQ_API_KEY` | Yes | Groq API key for the LLM |
| `GROQ_MODEL` | No | Model name (default: `llama-3.3-70b-versatile`) |
| `VAPI_API_KEY` | Yes | Vapi API key for telephony |
| `VAPI_ASSISTANT_ID` | No | Created by `setup_vapi` script |
| `VAPI_PHONE_NUMBER_ID` | No | Created by `setup_vapi` script |
| `PUBLIC_BASE_URL` | Yes | Public URL where backend is reachable |
| `PORT` | No | Server port (default: 8000) |
| `LOG_LEVEL` | No | Logging level (default: info) |

## API Endpoints

All responses use a consistent envelope: `{ "data": {...}, "error": null }`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/patients` | List all patients. Query params: `?last_name=`, `?date_of_birth=`, `?phone_number=` |
| `GET` | `/patients/:id` | Get a single patient by UUID |
| `POST` | `/patients` | Create a new patient |
| `PUT` | `/patients/:id` | Update a patient (partial updates allowed) |
| `DELETE` | `/patients/:id` | Soft-delete a patient (sets `deleted_at`) |
| `GET` | `/patients/:id/appointment` | Get appointment for a patient |
| `POST` | `/patients/:id/appointment` | Schedule an appointment |
| `GET` | `/calls` | List recent call logs |
| `GET` | `/calls/:id` | Get a single call log with transcript |
| `POST` | `/vapi/webhook` | Vapi webhook (tool calls + call events) |
| `GET` | `/health` | Health check |

## Patient Data Model

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `first_name` | String | Yes | 1–50 chars, alphabetic + hyphens/apostrophes |
| `last_name` | String | Yes | 1–50 chars, alphabetic + hyphens/apostrophes |
| `date_of_birth` | Date | Yes | Valid past date, MM/DD/YYYY |
| `sex` | Enum | Yes | Male, Female, Other, Decline to Answer |
| `phone_number` | String | Yes | Valid 10-digit US phone |
| `email` | String | No | Valid email format |
| `address_line_1` | String | Yes | Street address |
| `address_line_2` | String | No | Apt/Suite/Unit |
| `city` | String | Yes | 1–100 characters |
| `state` | String | Yes | 2-letter US state abbreviation |
| `zip_code` | String | Yes | 5-digit or ZIP+4 |
| `insurance_provider` | String | No | Insurance company name |
| `insurance_member_id` | String | No | Alphanumeric member ID |
| `preferred_language` | String | No | Default: English |
| `emergency_contact_name` | String | No | Full name |
| `emergency_contact_phone` | String | No | 10-digit US phone |
| `patient_id` | UUID | Auto | Auto-generated |
| `created_at` | Timestamp | Auto | UTC |
| `updated_at` | Timestamp | Auto | UTC |
| `deleted_at` | Timestamp | Auto | Soft-delete timestamp |

## Voice Agent Prompt

The system prompt is in [`app/voice_prompt.py`](app/voice_prompt.py). It instructs the agent to:
- Conduct a natural conversation (not IVR)
- Collect required fields 1–2 at a time
- Offer optional fields after required ones are complete
- Read back all information and confirm before saving
- Handle corrections, invalid data, and re-prompts
- Recognize returning callers by phone number (duplicate detection)
- Offer appointment scheduling after registration

## Bonus Features Implemented

- ✅ **Duplicate Detection** — Agent recognizes returning callers by phone number and offers to update
- ✅ **Dashboard UI** — Redesigned web dashboard with dark sidebar, stat cards, patient cards grid, call history, and transcript modal with chat-style bubbles
- ✅ **Call Transcript Logging** — Every call's transcript and summary stored in the database
- ✅ **Appointment Scheduling** — Agent can schedule a first appointment after registration
- ✅ **Automated Tests** — 40+ tests covering API CRUD, validation, webhook, and appointments
- ✅ **PostgreSQL Production DB** — Persistent storage via Render Postgres (survives restarts)
- ✅ **Barge-in Responsiveness** — Tuned endpointing (200ms), max tokens (200), voice speed (1.1x) for natural conversation flow
- ✅ **Vapi Webhook Event Handling** — Handles `assistant.started`, `end-of-call`, and tool call events with deduplication

## Running Tests

```bash
pytest -v
```

## Deployment (Render)

### Database Setup

1. Create a PostgreSQL database on Render (dashboard → New → PostgreSQL)
2. Copy the **Internal Database URL** connection string
3. Set it as the `DATABASE_URL` environment variable in your web service

> **Important:** Render's free tier does NOT support persistent disks. SQLite stored
> in the container filesystem will be wiped on every redeploy/cold start. Using
> Render Postgres ensures your data survives restarts.

### Web Service Setup

1. Push this repo to GitHub
2. Create a new Web Service on [Render](https://render.com)
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn app.api:app --host 0.0.0.0 --port $PORT`
5. Add environment variables (see table above)
6. Set `DATABASE_URL` to your Render Postgres connection string
7. Set `PUBLIC_BASE_URL` to your Render URL (e.g. `https://cc-va.onrender.com`)
8. On first deploy, `init_db()` automatically creates all tables in Postgres

Alternatively, use the included `render.yaml` for Blueprint deployment.

### Vapi Webhook Configuration

After deploying, update the Vapi assistant webhook URL to point to your Render URL:

```bash
PUBLIC_BASE_URL=https://cc-va.onrender.com python -m app.setup_vapi
```

This updates the Vapi assistant with the correct webhook URL and voice agent settings
(barge-in responsiveness, endpointing, voice speed). The script skips updates when
`PUBLIC_BASE_URL` contains `localhost` or `127.0.0.1` to avoid overwriting prod config.

## Project Structure

```
voice-ai-patient-registration/
├── app/
│   ├── __init__.py
│   ├── api.py              # FastAPI app entrypoint
│   ├── config.py           # Environment configuration
│   ├── database.py         # SQLAlchemy engine & session
│   ├── models.py           # ORM models (Patient, CallLog, Appointment)
│   ├── schemas.py          # Pydantic schemas with validation
│   ├── services.py         # Business logic layer
│   ├── seed.py             # Demo data seeding
│   ├── setup_vapi.py       # Vapi assistant + phone number provisioning
│   ├── voice_prompt.py     # System prompt & tool definitions
│   ├── routers/
│   │   ├── patients_router.py  # Patient CRUD endpoints
│   │   ├── calls_router.py     # Call log endpoints
│   │   └── vapi_router.py      # Vapi webhook handler
│   └── static/
│       └── index.html      # Dashboard UI
├── tests/
│   ├── conftest.py
│   ├── test_patients_api.py
│   ├── test_vapi_webhook.py
│   └── test_appointments.py
├── requirements.txt
├── .env.example
├── render.yaml
└── README.md
```

## Known Limitations & Trade-offs

1. **SQLite**: Chosen for simplicity and zero-config. In production, PostgreSQL would be preferred for concurrent writes. The `DATABASE_URL` is configurable, so swapping is trivial.

2. **Vapi dependency**: The voice agent requires Vapi for telephony. If Vapi is unavailable, the REST API and dashboard still work — only the voice channel is affected.

3. **No authentication on API**: The REST API has no auth layer. In production, add JWT or API key auth.

4. **No HIPAA compliance**: As stated in the challenge, this is a technical assessment, not a production healthcare system. Do not store real patient data.

5. **Groq rate limits**: Groq's free tier may rate-limit under heavy use. The model is configurable via `GROQ_MODEL`.

6. **Phone number provisioning**: Vapi may require a linked Twilio account to provision numbers. The `setup_vapi` script handles this gracefully and provides manual instructions if automatic provisioning fails.

## Observability

- All patient registrations are logged to stdout with patient ID and name
- All Vapi webhook events are logged (truncated to 2000 chars)
- Call transcripts and summaries are persisted to the `call_logs` table
- Structured logging throughout with timestamps and log levels
