# Deep Research API — Developer Documentation

Welcome to the **Deep Research API**, a self-hosted, privacy-first Research-as-a-Service API. It exposes a single-purpose REST API and a beautiful web UI: given a query, it runs a multi-round loop (plan queries → search → fetch webpages → extract facts → synthesize findings) and generates a structured, cited report, running entirely inside your infrastructure.

### New: Bring Your Own Key (BYOK) & Premium UI
You can now use the Deep Research API instantly without setting up a multi-tenant organization. Just open `examples/deep-research-premium.html` in your browser, paste your own **OpenAI, Anthropic, Gemini, or OpenRouter** API Key directly into the UI, and start an end-to-end research loop with an interactive chat feature!
---

## 1. Folder Structure

```
deep-research-api/
├── api/                    # FastAPI web server layer
│   ├── app.py              # Application entrypoint & middlewares
│   ├── middleware/         # Auth, audit log, rate limits
│   └── routes/             # REST endpoints (research, reports, sources, webhooks)
│
├── core/                   # Core business logic (framework-agnostic)
│   ├── llm/                # Unified LLMClient & providers (OpenAI, Anthropic, OpenRouter)
│   ├── research/           # Research orchestrator engine, planner, extractor, synthesizer
│   ├── queue/              # Worker configurations, ARQ task definitions
│   └── webhooks/           # Webhook signature signing and dispatch logic
│
├── db/                     # Database persistence layer
│   ├── engine.py           # Async SQLAlchemy connection
│   ├── models/             # DB schema tables (Jobs, Reports, Sources, Webhooks, Usage)
│   └── migrations/         # Alembic database migrations
│
├── integrations/           # External fetchers & search clients (SearXNG client, URL HTML fetcher)
├── scripts/                # Utility scripts (migrations execution, db seeding)
├── deploy/                 # Docker Compose & container configurations
└── tests/                  # Unit, integration, and E2E test suites
```

---

## 2. Prerequisites
Before beginning, ensure you have the following installed:
- **Python 3.11+**
- **uv** (Python package installer and manager)
- **PostgreSQL** (Active instance)
- **Redis** (Used for job queueing and webhook retry schedules)
- **SearXNG** (Self-hosted search engine, required for local execution fallback)

---

## 3. Local Development Setup

### Step 1: Configuration
Copy `.env.example` to `.env` and fill in your local coordinates:
```bash
cp .env.example .env
```
Example configuration:
```ini
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/drapi
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=use-a-secure-32-character-key-here
ENVIRONMENT=development
SEARXNG_URL=http://localhost:8080
```

### Step 2: Install Dependencies & Apply Migrations
Use `uv` to install dependencies and run Alembic migrations to construct the database schema:
```bash
uv pip install -r requirements.txt
uv run python scripts/migrate.py
```

### Step 3: Seed Credentials (Optional for BYOK)
If you want to use the multi-tenant Organization features, initialize a tenant organization and configure a default LLM backend:
```bash
uv run python scripts/seed.py \
  --org-name "Acme Corp" \
  --backend-provider "openai" \
  --backend-key "sk-proj-YOUR-OPENAI-KEY" \
  --backend-model "gpt-4o"
```
*Note down the generated **API Key** (e.g. `drapi_live_...`) and the **Org ID**.*

*(If you just want to use your own LLM keys on the fly, you can skip this step and use the BYOK flow in the Web UI).*

### Step 4: Run Services
You need to run two processes concurrently in development:

1. **Start the API Server**:
   ```bash
   uv run uvicorn api.app:app --reload --port 8000
   ```
2. **Start the Queue Worker**:
   ```bash
   uv run arq core.queue.worker.WorkerSettings
   ```

---

## 4. Running with Docker Compose (Production-like Setup)

The entire system stack can be spun up as Docker containers in a single command. The Docker configuration is set up to run database migrations automatically upon container start.

1. **Launch containers**:
   ```bash
   cd deploy
   docker compose up -d --build
   ```
2. **Seed the database inside the container**:
   ```bash
   docker compose exec api python scripts/seed.py \
     --org-name "Acme Corp" \
     --backend-provider "openai" \
     --backend-key "sk-proj-YOUR-OPENAI-KEY" \
     --backend-model "gpt-4o"
   ```

---

## 5. API Reference Quickstart

Include your API key as a Bearer token in the `Authorization` header: `Authorization: Bearer YOUR_API_KEY`.

### Submit a Research Job
- **Endpoint**: `POST /v1/research`
- **Request Body**:
  ```json
  {
    "query": "Key competitors in the solid-state battery space as of 2026",
    "max_rounds": 2,
    "priority": 3
  }
  ```
- **Response**: `202 Accepted` returning a `job_id`.

### Poll Job Status
- **Endpoint**: `GET /v1/research/{job_id}`
- **Response**: Returns current status (`queued`, `running`, `completed`, `failed`). When completed, the response includes the `report` summary, content markdown, and citations list.

### List Cited Sources
- **Endpoint**: `GET /v1/research/{job_id}/sources`
- **Response**: Lists URL, Title, round number, and excerpt snippets extracted from all cited pages for this job.

### Export Report Markdown
- **Endpoint**: `GET /v1/reports/{report_id}/export?format=md`
- **Response**: Plaintext markdown attachment download.

### Chat with Report
- **Endpoint**: `POST /v1/research/{job_id}/chat`
- **Request Body**:
  ```json
  {
    "message": "What does the report say about AlphaFold?",
    "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
  }
  ```
- **Response**: `{"response": "Based on the report, AlphaFold..."}`

### Cancel Job Execution
- **Endpoint**: `DELETE /v1/research/{job_id}`
- **Response**: `204 No Content` (aborts worker run loop).

---

## 6. Webhooks System

You can dynamically manage webhook subscriptions per organization using the following endpoints:
- **Register Webhook**: `POST /v1/webhooks` with `{ "url": "https://callback.com", "secret": "secret" }`.
- **List Webhooks**: `GET /v1/webhooks`.
- **Remove Webhook**: `DELETE /v1/webhooks/{webhook_id}`.

### Payload Format & Signature
When a job completes or fails, active webhooks are dispatched with the following payload structure:
```json
{
  "event": "research.completed",
  "job_id": "job_123",
  "status": "completed",
  "org_id": "org_abc",
  "query": "query text...",
  "created_at": "2026-06-07T10:18:00Z",
  "finished_at": "2026-06-07T10:19:15Z",
  "metadata": {},
  "report_url": "/v1/reports/rpt_xyz"
}
```
Each POST request includes an `X-Signature` header calculated as:
```
X-Signature: sha256=<hmac_hex_hash_using_webhook_secret>
```

---

## 7. Testing

To execute tests:

- **Run non-E2E (Unit & Integration) tests**:
  ```bash
  uv run pytest -m "not e2e"
  ```
- **Run E2E tests** (requires live Docker compose stack):
  ```bash
  $env:E2E_API_KEY="drapi_live_..."
  uv run pytest
  ```
