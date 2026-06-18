# Vanta — (v1.0)

Welcome to **Vanta**, a self-hosted, privacy-first Research-as-a-Service API. Built as a Queue-Based Modular Monolith, it runs a sophisticated multi-agent loop (Coordinator → Search → Validate → Extract → Contradiction → Cite → Synthesize) and generates a structured, cited report, running entirely inside your infrastructure.

### Bring Your Own Key (BYOK)

Pass your **OpenAI, Anthropic, Gemini, or OpenRouter** API key as a Bearer token and start researching. The system auto-detects the provider and intelligently scales its worker pool.

---

## 1. Architecture Overview

Vanta uses an asynchronous, native agent architecture without relying on heavy frameworks like LangChain or CrewAI. It leverages a global knowledge graph backed by PostgreSQL and pgvector, an in-memory message bus for event-driven agent decoupling, and ARQ/Redis for robust task queuing.

### Multi-Agent Pipeline

The core research loop is orchestrated by `engine.py`, executing the following agents:

1. **CoordinatorAgent**: Decides whether to `CONTINUE` researching or `SYNTHESIZE` based on current findings vs. maximum rounds.
2. **SearchAgent**: Generates semantic and keyword queries to fill knowledge gaps.
3. **ValidatorAgent**: Assigns a hybrid heuristic+LLM `trust_score` to sources, filtering out low-quality or untrustworthy domains.
4. **ExtractorAgent**: Pulls structured `Claim` objects from HTML, evaluating against historical claims to detect overlaps or contradictions.
5. **ContradictionAgent**: Evaluates the global state to explicitly highlight and suggest resolutions for conflicting facts across sources.
6. **SynthesizerAgent**: Compiles findings into a comprehensive Markdown report.
7. **CitationVerifierAgent**: Runs a native validation pass to strictly enforce and correct inline citation mappings.

### Plugin Extensibility

`core/plugins/registry.py` allows dynamic runtime loading of customized `BaseSearchPlugin` and `BaseExtractorPlugin` implementations, enabling simple drop-in integrations with proprietary datasets or private search engines.

---

## 2. Folder Structure

```
deep-research-api/
├── api/                    # FastAPI web server layer
│   ├── app.py              # Application entrypoint & middlewares
│   ├── middleware/         # Auth (BYOK detection), audit log, tracing
│   └── routes/             # REST endpoints (research, reports, sources, webhooks)
│
├── core/                   # Core business logic (framework-agnostic)
│   ├── llm/                # Unified LLMClient & providers
│   ├── research/           # Agent orchestration, state machine, vector memory
│   │   ├── agents/         # Search, Validator, Extractor, Contradiction, Synthesizer
│   │   ├── engine.py       # Main orchestrator loop
│   │   └── memory.py       # Postgres pgvector knowledge graph integration
│   ├── queue/              # Worker configurations, ARQ task definitions
│   ├── plugins/            # Plugin base classes and dynamic registry
│   └── webhooks/           # Webhook signature signing and dispatch logic
│
├── db/                     # Database persistence layer
│   ├── engine.py           # Async SQLAlchemy connection
│   ├── models/             # DB schema tables (Jobs, Reports, Sources, Claims, Usage)
│   └── migrations/         # Alembic database migrations
│
├── integrations/           # External fetchers (Playwright rendering) & search
├── scripts/                # Utility scripts (migrations execution)
├── deploy/                 # Docker Compose & container configurations
└── tests/                  # Unit, integration, and E2E test suites
```

---

## 3. Prerequisites

Before beginning, ensure you have the following installed:

- **Docker & Docker Compose** (Recommended for production)
- **Python 3.12+**
- **uv** (Python package installer and manager)
- **PostgreSQL** (with pgvector extension enabled)
- **Redis** (Used for job queueing)
- **SearXNG** (Self-hosted search engine)

---

## 4. Quick Start (Clone & Run)

### Using Docker Compose (Recommended)

The entire system stack can be spun up as Docker containers in a single command, automatically provisioning Postgres+pgvector, Redis, and SearXNG alongside the API and Worker.

```bash
git clone <repo-url>
cd deep-research-api/deploy
cp .env.example .env

# Start the stack (API, Worker, DB, Redis, SearXNG)
docker compose up -d --build
```

The API will be available at `http://localhost:8000`.

### Local Development Setup

If you prefer running the Python processes manually:

```bash
cp deploy/.env.example .env
uv pip install -r requirements.txt
playwright install chromium
playwright install-deps
uv run python scripts/migrate.py
```

Start the services:

```bash
# Terminal 1: API Server
uv run uvicorn api.app:app --reload --port 8000

# Terminal 2: Worker
uv run arq core.queue.worker.WorkerSettings
```

---

## 5. API Reference

All requests must pass your LLM API key as a Bearer token in the `Authorization` header: `Authorization: Bearer YOUR_LLM_API_KEY`.
The system auto-detects the provider from your key prefix (`sk-...`, `sk-ant-...`, `sk-or-...`, `AIza...`).

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
- **Response**: Returns current status (`queued`, `running`, `completed`, `failed`). Includes full report and partial sources when completed.

### Stream Progress (SSE)

- **Endpoint**: `GET /v1/research/{job_id}/stream`
- **Response**: Server-Sent Events detailing live progress percentage, status, and source counts.

### Export Report (PDF/Markdown)

- **Endpoint**: `GET /v1/reports/{report_id}/export?format=pdf` (Supports `md`, `pdf`, `json`)
- **Note**: PDF export utilizes `weasyprint` and `markdown2`.

### Global Knowledge Graph Search

- **Endpoint**: `GET /v1/knowledge-graph/search?q=quantum+computing&limit=10`
- **Response**: Searches the global vector database across all previous research sessions for matching verified Claims.

### Chat with Report

- **Endpoint**: `POST /v1/research/{job_id}/chat`
- **Request Body**:
  ```json
  {
    "message": "What does the report say about AlphaFold?"
  }
  ```

---

## 6. Webhooks

Vanta securely dispatches HMAC-SHA256 signed webhooks (with replay protection via `X-Webhook-Timestamp`) upon job completion/failure.

- **Register**: `POST /v1/webhooks` with `{ "url": "https://callback.com", "secret": "secret" }`.
- **List**: `GET /v1/webhooks`.
- **Remove**: `DELETE /v1/webhooks/{webhook_id}`.

---

## 7. Using Local Models (Ollama, vLLM, etc.)

Any OpenAI-compatible local server works out of the box. Just set the `X-Provider`, `X-Base-Url`, and `X-Model` headers:

```bash
curl -X POST http://localhost:8000/v1/research \
  -H "Authorization: Bearer dummy-key" \
  -H "X-Provider: openai_compatible" \
  -H "X-Base-Url: http://localhost:11434/v1" \
  -H "X-Model: llama3" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is quantum computing?", "max_rounds": 1}'
```

---

## 8. Developer CLI

Vanta includes a built-in command-line interface (`cli.py`) for submitting jobs and tracking progress directly from your terminal.

```bash
uv run python cli.py submit "What are the latest advancements in quantum computing?" \
  --api-key "sk-..." \
  --max-rounds 2 \
  --api-url "http://localhost:8000"
```

The CLI streams live SSE progress directly to `stdout` and pretty-prints the final markdown report upon completion.

---

## 9. Example Web Clients

We provide several drop-in examples of how to consume the Vanta API:

1. **Vanta Console**: Served directly at `http://localhost:8000/`. A simple, clean debugging interface to run research and view JSON logs.
2. **Premium Platform UI**: Open `examples/deep-research-platform.html` in your browser. A rich, dynamic frontend showcasing how a commercial product might integrate the API, featuring glassmorphism, animations, and PDF exports.
3. **Third-Party Client**: Open `examples/third-party-client.html`. Demonstrates how an entirely separate SaaS product can securely dispatch research queries to the API behind the scenes.
