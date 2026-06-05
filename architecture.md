# Deep Research API — Full Architecture Document

> Self-hosted, privacy-first research-as-a-service built on the Odysseus IterResearch engine.  
> Designed for enterprise deployment inside customer VPCs, air-gapped networks, and on-prem infra.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [File & Folder Structure](#2-file--folder-structure)
3. [Service Architecture](#3-service-architecture)
4. [Component Deep-Dives](#4-component-deep-dives)
5. [State & Storage Map](#5-state--storage-map)
6. [Service Connection Diagram](#6-service-connection-diagram)
7. [API Contract](#7-api-contract)
8. [LLM Backend Strategy](#8-llm-backend-strategy)
9. [Auth & Multi-Tenancy](#9-auth--multi-tenancy)
10. [Deployment Topology](#10-deployment-topology)
11. [What You Strip from Odysseus](#11-what-you-strip-from-odysseus)
12. [Build Sequence](#12-build-sequence)

---

## 1. System Overview

This is a **single-purpose, API-first service** extracted and hardened from Odysseus's deep research subsystem. It exposes one core capability: given a natural language query, run a multi-round iterative research loop (search → fetch → extract → synthesize) and return a structured, cited report — entirely inside the customer's infrastructure.

### Core loop (IterResearch, unchanged from Odysseus)

```
POST /v1/research
        │
        ▼
   Plan queries          ← LLM call #1: decompose question into sub-queries
        │
        ▼
   Search sources        ← SearXNG (local) or Brave/Tavily (external, optional)
        │
        ▼
   Fetch & extract       ← httpx + LLM call #2: pull key facts from each page
        │
        ▼
   Synthesize round      ← LLM call #3: merge findings, assess gaps
        │
        ▼
   Continue? (LLM)       ← up to N rounds (configurable, default 3)
        │
        ▼
   Final report          ← structured JSON + markdown/DOCX/PDF export
        │
        ▼
   Webhook callback      ← POST to customer endpoint with job result
```

### Non-goals (explicitly out of scope for v1)

- No chat UI (this is a pure API product)
- No email / calendar / notes integrations (Odysseus features not needed)
- No local LLM serving management (Cookbook stripped out)
- No user-facing frontend beyond an admin dashboard for job monitoring

---

## 2. File & Folder Structure

```
deep-research-api/
│
├── api/                          # FastAPI application layer
│   ├── __init__.py
│   ├── app.py                    # Entrypoint: lifespan, router mount, middleware
│   ├── dependencies.py           # Shared FastAPI deps: db session, current org, rate limit
│   │
│   ├── routes/
│   │   ├── research.py           # POST /v1/research, GET /v1/research/{id}, DELETE
│   │   ├── reports.py            # GET /v1/reports/{id}/export?format=docx|pdf|md|json
│   │   ├── sources.py            # GET /v1/research/{id}/sources  (cited URLs + metadata)
│   │   ├── audit.py              # GET /v1/audit  (admin: full query + source log)
│   │   ├── health.py             # GET /health, GET /health/ready, GET /health/live
│   │   ├── admin/
│   │   │   ├── orgs.py           # CRUD for tenant organisations
│   │   │   ├── api_keys.py       # Issue / revoke API keys per org
│   │   │   ├── llm_backends.py   # Register / test LLM endpoint per org
│   │   │   └── usage.py          # Per-org report count, token usage, billing export
│   │   └── webhooks.py           # CRUD for webhook endpoints per org
│   │
│   └── middleware/
│       ├── auth.py               # API key extraction → org context injection
│       ├── rate_limit.py         # Sliding window rate limiter (Redis-backed)
│       ├── audit_log.py          # Request/response logger → AuditLog table
│       └── security_headers.py   # CSP, HSTS, X-Frame-Options, nosniff
│
├── core/                         # Business logic — framework-agnostic
│   ├── research/
│   │   ├── engine.py             # IterResearch orchestrator (ported from Odysseus)
│   │   ├── planner.py            # LLM call: decompose query into sub-queries
│   │   ├── searcher.py           # Search provider abstraction (SearXNG / Brave / Tavily)
│   │   ├── fetcher.py            # Async URL fetcher with semaphore concurrency control
│   │   ├── extractor.py          # LLM call: extract key facts from raw page content
│   │   ├── synthesizer.py        # LLM call: merge rounds, write final report
│   │   ├── category_detector.py  # Classify query type → apply format override prompt
│   │   └── report_formatter.py   # Render findings → ReportOutput schema
│   │
│   ├── export/
│   │   ├── markdown.py           # Render report as .md with footnotes
│   │   ├── docx.py               # python-docx: report → .docx with sources table
│   │   ├── pdf.py                # weasyprint: .html → .pdf
│   │   └── json.py               # Structured JSON with citations array
│   │
│   ├── queue/
│   │   ├── worker.py             # ARQ worker: pull jobs, run engine, update DB
│   │   ├── tasks.py              # ARQ task definitions: run_research_job
│   │   └── scheduler.py          # ARQ cron: cleanup expired jobs, retry stuck jobs
│   │
│   ├── webhooks/
│   │   ├── dispatcher.py         # POST job result to registered webhook URL
│   │   └── signing.py            # HMAC-SHA256 signature on webhook payload
│   │
│   ├── llm/
│   │   ├── client.py             # Unified LLM abstraction (ported from Odysseus llm_core.py)
│   │   ├── providers/
│   │   │   ├── openai.py         # OpenAI + Azure OpenAI + any OpenAI-compatible endpoint
│   │   │   ├── anthropic.py      # Anthropic native (with prompt caching)
│   │   │   └── ollama.py         # Local Ollama server
│   │   ├── prompt_security.py    # Wrap untrusted content (fetched pages) in fences
│   │   └── context_sizing.py     # Map model name → context window size
│   │
│   └── security/
│       ├── api_keys.py           # Key generation (32-byte hex), hashing (bcrypt), validation
│       └── encryption.py         # Fernet: encrypt/decrypt sensitive DB fields
│
├── db/                           # Database layer
│   ├── engine.py                 # SQLAlchemy async engine setup (PostgreSQL)
│   ├── session.py                # AsyncSession factory
│   ├── models/
│   │   ├── org.py                # Organisation (tenant)
│   │   ├── api_key.py            # APIKey (hashed, scoped)
│   │   ├── research_job.py       # ResearchJob (queue item + result storage)
│   │   ├── report.py             # Report (rendered output, export cache)
│   │   ├── source.py             # Source (URL, title, excerpt, cited by job)
│   │   ├── webhook.py            # WebhookEndpoint (per org)
│   │   ├── audit_log.py          # AuditLog (every API request, immutable)
│   │   ├── llm_backend.py        # LLMBackend (per org, encrypted api_key)
│   │   └── usage.py              # UsageRecord (per job: tokens in/out, duration)
│   └── migrations/
│       ├── env.py                # Alembic env (async)
│       └── versions/             # Auto-generated migration scripts
│
├── integrations/                 # External search + fetch adapters
│   ├── searxng.py                # SearXNG REST client (self-hosted)
│   ├── brave.py                  # Brave Search API client
│   ├── tavily.py                 # Tavily API client (fallback)
│   └── fetcher.py                # httpx AsyncClient: fetch + strip HTML → plain text
│
├── admin/                        # Lightweight admin dashboard (server-rendered HTML)
│   ├── app.py                    # Starlette admin routes
│   ├── templates/
│   │   ├── base.html
│   │   ├── jobs.html             # Live job monitor table
│   │   ├── audit.html            # Audit log viewer with filters
│   │   └── usage.html            # Per-org usage and export
│   └── static/
│       └── admin.css
│
├── tests/
│   ├── unit/
│   │   ├── test_planner.py
│   │   ├── test_synthesizer.py
│   │   ├── test_export_docx.py
│   │   └── test_api_key_auth.py
│   ├── integration/
│   │   ├── test_research_endpoint.py
│   │   ├── test_webhook_dispatch.py
│   │   └── test_audit_log.py
│   └── fixtures/
│       ├── mock_llm.py           # Deterministic LLM stub for tests
│       └── mock_searxng.py       # Static search result fixture
│
├── deploy/
│   ├── docker-compose.yml        # Full stack: API + worker + Redis + Postgres + SearXNG
│   ├── docker-compose.airgap.yml # Air-gap variant: Ollama instead of external LLM
│   ├── Dockerfile                # Multi-stage: builder + slim runtime
│   ├── Dockerfile.worker         # ARQ worker image (same codebase, different entrypoint)
│   ├── k8s/
│   │   ├── namespace.yaml
│   │   ├── api-deployment.yaml
│   │   ├── worker-deployment.yaml
│   │   ├── postgres-statefulset.yaml
│   │   ├── redis-statefulset.yaml
│   │   └── ingress.yaml
│   └── helm/
│       └── deep-research/        # Helm chart for enterprise k8s deploy
│
├── docs/
│   ├── openapi.yaml              # Hand-maintained OpenAPI 3.1 spec (source of truth)
│   ├── quickstart.md
│   ├── integration-guide.md
│   └── security.md               # Data flow, what leaves the network, threat model
│
├── .env.example
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── README.md
```

---

## 3. Service Architecture

The production stack is four processes communicating through two shared data stores.

```
┌─────────────────────────────────────────────────────────────────┐
│  Customer network boundary                                       │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │  API server  │    │  ARQ worker  │    │  Admin dashboard  │  │
│  │  (FastAPI)   │    │  (async job  │    │  (Starlette HTML) │  │
│  │  :8000       │    │   executor)  │    │  :8001            │  │
│  └──────┬───────┘    └──────┬───────┘    └────────┬──────────┘  │
│         │                   │                     │             │
│         └──────────┬────────┘─────────────────────┘             │
│                    │                                             │
│         ┌──────────▼──────────┐    ┌──────────────────────┐     │
│         │  PostgreSQL         │    │  Redis               │     │
│         │  (jobs, reports,    │    │  (job queue, rate     │     │
│         │   audit, orgs)      │    │   limit counters,    │     │
│         └─────────────────────┘    │   webhook retry)     │     │
│                                    └──────────────────────┘     │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  Optional local services (customer-managed)               │   │
│  │  SearXNG (:8080)    Ollama (:11434)    pgvector extension │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
         │ outbound only, optional
         ▼
  Brave Search API / Tavily API / Azure OpenAI / Anthropic API
  (customer decides which external services are permitted)
```

### Process responsibilities

| Process    | Responsibility                                              | Scales                                    |
| ---------- | ----------------------------------------------------------- | ----------------------------------------- |
| `api`      | Accept requests, enqueue jobs, serve results, handle auth   | Horizontally (stateless)                  |
| `worker`   | Execute IterResearch jobs, write results, fire webhooks     | Horizontally (add workers for throughput) |
| `admin`    | Internal dashboard: job monitor, audit viewer, usage export | Single instance, internal network only    |
| `postgres` | Persistent state: all jobs, reports, audit, org data        | Vertical + read replicas                  |
| `redis`    | Job queue (ARQ), rate limit counters, webhook retry queue   | Single instance or Sentinel               |

---

## 4. Component Deep-Dives

### 4.1 `core/research/engine.py` — IterResearch orchestrator

This is the direct port of `src/deep_research.py` from Odysseus, refactored for:

- Async-first with structured cancellation (receives a `CancellationToken`)
- Progress callbacks (`on_round_complete`) that write partial results to DB as rounds finish
- No dependency on Odysseus's session/chat/memory system

```python
class IterResearchEngine:
    async def run(
        self,
        job: ResearchJob,
        llm: LLMClient,
        searcher: SearchProvider,
        on_progress: Callable[[RoundResult], Awaitable[None]],
        cancel: CancellationToken,
    ) -> ReportOutput:
        plan = await self.planner.plan(job.query, llm)
        findings: list[Finding] = []

        for round_n in range(job.max_rounds):
            if cancel.is_set():
                break
            queries = await self.planner.next_queries(plan, findings, llm)
            raw_results = await self.searcher.search_all(queries, searcher)
            extracted = await self.extractor.extract_all(raw_results, llm)
            findings.extend(extracted)
            should_continue = await self.synthesizer.should_continue(findings, llm)
            await on_progress(RoundResult(round=round_n, findings=findings))
            if not should_continue:
                break

        return await self.synthesizer.final_report(job.query, findings, llm)
```

Key design choices:

- `on_progress` writes to DB after each round — a customer can poll `GET /v1/research/{id}` and see partial results as they stream in, without needing an SSE connection.
- `CancellationToken` allows `DELETE /v1/research/{id}` to cleanly abort a running job.
- All LLM calls go through the unified `LLMClient` — the engine has zero provider-specific code.

### 4.2 `core/queue/worker.py` — ARQ job executor

ARQ (async Redis queue) handles job dispatch. The worker function is minimal:

```python
async def run_research_job(ctx: dict, job_id: str) -> None:
    async with get_db_session() as db:
        job = await db.get(ResearchJob, job_id)
        job.status = "running"
        job.started_at = utcnow()
        await db.commit()

        try:
            engine = IterResearchEngine()
            llm = LLMClient.for_org(job.org_id, db)
            searcher = SearchProvider.from_config(settings)
            cancel = CancellationToken(job_id)

            report = await engine.run(
                job=job,
                llm=llm,
                searcher=searcher,
                on_progress=partial(write_partial_result, db, job),
                cancel=cancel,
            )

            job.status = "completed"
            job.report = report
            await db.commit()
            await WebhookDispatcher.fire(job)

        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            await db.commit()
            await WebhookDispatcher.fire_error(job, exc)
```

Retry logic: ARQ retries failed jobs up to 3 times with exponential backoff. After max retries, job is marked `failed` and webhook fires with `{"status": "failed", "error": "..."}`.

### 4.3 `db/models/research_job.py` — central state object

```python
class ResearchJob(Base):
    __tablename__ = "research_jobs"

    id: str                    # UUID, primary key
    org_id: str                # FK → Organisation
    api_key_id: str            # FK → APIKey (which key submitted this job)
    query: str                 # Original natural language query
    status: str                # queued | running | completed | failed | cancelled
    priority: int              # 1 (high) to 5 (low), default 3
    max_rounds: int            # IterResearch iteration cap, default 3
    model_override: str | None # Optional: use a specific model for this job
    category: str | None       # Detected: product | comparison | howto | factcheck | general
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None

    # Relationships
    report: Report             # One-to-one, written on completion
    sources: list[Source]      # All URLs fetched, written incrementally
    usage: UsageRecord         # Token counts, written on completion
```

### 4.4 `db/models/audit_log.py` — immutable request log

The audit log is append-only. No UPDATE or DELETE queries ever touch it. This is the table the security reviewer asks to see.

```python
class AuditLog(Base):
    __tablename__ = "audit_log"

    id: int                    # Auto-increment (not UUID — sequential for export)
    org_id: str
    api_key_id: str
    method: str                # GET | POST | DELETE
    path: str                  # /v1/research, /v1/reports/123/export, etc.
    query_text: str | None     # For POST /v1/research: the submitted query
    response_status: int       # HTTP status code
    duration_ms: int
    ip_address: str            # Customer internal IP of the API caller
    user_agent: str
    timestamp: datetime        # UTC, indexed
```

Exported nightly as a compressed JSONL file to `data/audit/YYYY-MM-DD.jsonl.gz`. Retention configurable (default 365 days).

### 4.5 `core/webhooks/dispatcher.py` — delivery with retry

```python
async def fire(job: ResearchJob) -> None:
    endpoints = await get_webhooks_for_org(job.org_id)
    for endpoint in endpoints:
        payload = WebhookPayload(
            event="research.completed",
            job_id=job.id,
            status=job.status,
            report_url=f"/v1/reports/{job.report.id}",
            query=job.query,
            created_at=job.created_at.isoformat(),
            finished_at=job.finished_at.isoformat(),
        )
        signature = hmac_sign(payload, endpoint.secret)
        await redis.enqueue_webhook(endpoint.url, payload, signature, retries=5)
```

HMAC signing: every webhook POST includes `X-Signature: sha256=<hex>` computed over the JSON body. Customers verify this in their receiver. Retry schedule: 10s, 30s, 2m, 10m, 1h. After 5 failures, the endpoint is marked `degraded` and an admin alert fires.

### 4.6 `core/export/docx.py` — the enterprise-critical output

The DOCX export is what gets a report from the API into a partner's hands. It must include:

- Title, executive summary (first 3 sentences of synthesis)
- Numbered findings sections with inline citation markers
- Sources table at the end: `[1] | Title | URL | Fetched at`
- Metadata footer: query, model, timestamp, org name

Built with `python-docx`. The structure maps directly from `ReportOutput.sections` and `ReportOutput.citations`.

---

## 5. State & Storage Map

| Data                    | Where it lives                   | Format                               | TTL / Retention                   |
| ----------------------- | -------------------------------- | ------------------------------------ | --------------------------------- |
| Research jobs           | PostgreSQL `research_jobs`       | Row                                  | Forever (soft-delete only)        |
| Report content          | PostgreSQL `reports`             | Text (markdown) + JSONB (structured) | Forever                           |
| Fetched source cache    | PostgreSQL `sources`             | Text excerpt + URL                   | Per-job, cleaned on job delete    |
| Org / API key config    | PostgreSQL `orgs`, `api_keys`    | Rows, key hash bcrypt                | Forever                           |
| LLM backend creds       | PostgreSQL `llm_backends`        | Fernet-encrypted `api_key` field     | Until revoked                     |
| Audit log               | PostgreSQL `audit_log`           | Rows (append-only)                   | 365 days configurable             |
| Usage records           | PostgreSQL `usage_records`       | Rows                                 | Forever (billing source of truth) |
| Job queue               | Redis list (ARQ)                 | Serialized job args                  | Until consumed or TTL 24h         |
| Rate limit counters     | Redis hash                       | Sliding window counts                | 60s window, auto-expire           |
| Webhook retry queue     | Redis sorted set                 | Payload + retry timestamp            | Until delivered or max attempts   |
| Export cache (DOCX/PDF) | Local filesystem `data/exports/` | Binary file                          | 24h, then regenerated on request  |
| Audit export            | Local filesystem `data/audit/`   | `.jsonl.gz` per day                  | Configurable, default 365 days    |

### What never touches the filesystem

- The research query text
- Fetched page content (held in memory only during job execution, then discarded)
- LLM prompts and completions (logged to `audit_log` at query level only, not full prompt)

This is a deliberate privacy design decision. The audit log shows "who asked what and when" without storing the full retrieved content.

---

## 6. Service Connection Diagram

```
                        ┌─────────────────────────────────┐
  Customer system       │   API server (FastAPI :8000)     │
  (CI tool, script,  ──►│                                  │
   Zapier, n8n)         │  POST /v1/research               │
                        │    → validate API key (Redis)    │
                        │    → write ResearchJob (PG)      │
                        │    → enqueue job (Redis/ARQ)  ───┼──► Redis job queue
                        │    → return {job_id, status}     │
                        └─────────────────────────────────┘

  Customer system        ┌────────────────────────────────┐
  (polling or        ◄───│  GET /v1/research/{id}         │
   webhook)             │    → read job + partial report  │◄─── PostgreSQL
                        │    → return status + findings   │
                        └────────────────────────────────┘

                        ┌─────────────────────────────────┐
  Redis job queue  ────►│   ARQ Worker                    │
                        │                                  │
                        │  1. Fetch job from PG            │◄─── PostgreSQL
                        │  2. Build LLMClient for org      │◄─── LLMBackend (PG, decrypted)
                        │  3. Run IterResearchEngine       │
                        │     ├─ Planner  ────────────────►│ LLM endpoint (org-specific)
                        │     ├─ Searcher ────────────────►│ SearXNG / Brave / Tavily
                        │     ├─ Fetcher  ────────────────►│ Target URLs (httpx)
                        │     ├─ Extractor ───────────────►│ LLM endpoint
                        │     └─ Synthesizer ─────────────►│ LLM endpoint
                        │  4. Write Report + Sources → PG  │──► PostgreSQL
                        │  5. Write UsageRecord → PG       │──► PostgreSQL
                        │  6. Enqueue webhook → Redis      │──► Redis retry queue
                        └─────────────────────────────────┘

                        ┌─────────────────────────────────┐
  Redis retry queue ───►│   Webhook dispatcher (async)    │
                        │    → POST payload to endpoint   │──► Customer webhook URL
                        │    → HMAC-sign payload          │
                        │    → retry on failure (5x)      │
                        └─────────────────────────────────┘

                        ┌─────────────────────────────────┐
  Internal only     ───►│  Admin dashboard (:8001)        │
                        │    → Job monitor (live table)   │◄─── PostgreSQL
                        │    → Audit log viewer           │◄─── PostgreSQL
                        │    → Usage export CSV           │
                        │    → Org / key management       │
                        └─────────────────────────────────┘
```

---

## 7. API Contract

### Core endpoints

```
POST   /v1/research                  Submit a new research job
GET    /v1/research/{id}             Poll job status + partial/full results
DELETE /v1/research/{id}             Cancel a running job
GET    /v1/research/{id}/sources     List all sources fetched for a job

GET    /v1/reports/{id}              Get the final report (JSON)
GET    /v1/reports/{id}/export       Export report (?format=docx|pdf|md)

GET    /v1/usage                     Per-org usage summary (?from=&to=)
GET    /v1/audit                     Audit log entries (admin API key only)

POST   /v1/webhooks                  Register a webhook endpoint
GET    /v1/webhooks                  List webhook endpoints
DELETE /v1/webhooks/{id}             Remove a webhook endpoint
```

### Request: `POST /v1/research`

```json
{
  "query": "What are the competitive dynamics in the CAR-T cell therapy market as of 2025?",
  "max_rounds": 3,
  "priority": 2,
  "model_override": "gpt-4o",
  "export_formats": ["docx", "json"],
  "webhook_url": "https://ci-tool.internal/hooks/research",
  "metadata": {
    "requester": "analyst-team-a",
    "project_id": "proj_123"
  }
}
```

### Response: `GET /v1/research/{id}` (completed)

```json
{
  "id": "job_8f3a1c2d",
  "status": "completed",
  "query": "What are the competitive dynamics in the CAR-T cell therapy market...",
  "category": "comparison",
  "rounds_completed": 3,
  "created_at": "2025-06-05T10:00:00Z",
  "finished_at": "2025-06-05T10:03:42Z",
  "duration_seconds": 222,
  "report": {
    "id": "rpt_a9b2c1",
    "summary": "The CAR-T cell therapy market is dominated by four players...",
    "sections": [
      {
        "title": "Market leaders",
        "content": "Novartis (Kymriah) and Gilead/Kite (Yescarta) hold...",
        "citations": ["src_1", "src_3", "src_7"]
      }
    ],
    "export_urls": {
      "docx": "/v1/reports/rpt_a9b2c1/export?format=docx",
      "json": "/v1/reports/rpt_a9b2c1/export?format=json"
    }
  },
  "usage": {
    "tokens_in": 14820,
    "tokens_out": 3210,
    "sources_fetched": 18,
    "search_queries_issued": 9
  },
  "metadata": {
    "requester": "analyst-team-a",
    "project_id": "proj_123"
  }
}
```

### Webhook payload

```json
{
  "event": "research.completed",
  "job_id": "job_8f3a1c2d",
  "status": "completed",
  "org_id": "org_pharma_abc",
  "report_url": "/v1/reports/rpt_a9b2c1",
  "query": "What are the competitive dynamics...",
  "finished_at": "2025-06-05T10:03:42Z",
  "metadata": { "requester": "analyst-team-a", "project_id": "proj_123" }
}
```

Header: `X-Signature: sha256=<hmac_hex>`

---

## 8. LLM Backend Strategy

Every organisation registers one or more LLM backends. The worker resolves which backend to use for a given job at execution time.

```python
class LLMBackend(Base):
    id: str
    org_id: str
    name: str                  # "azure-gpt4o-prod", "ollama-local"
    provider: str              # openai | anthropic | ollama | openai_compatible
    base_url: str              # https://org.openai.azure.com or http://ollama:11434
    api_key: bytes             # Fernet-encrypted
    model: str                 # "gpt-4o", "claude-3-5-sonnet-20241022", "llama3.1:70b"
    is_default: bool
    max_concurrent: int        # Concurrency cap for this backend (default 3)
```

### Provider support matrix

| Provider            | Auth                               | Use case                                               |
| ------------------- | ---------------------------------- | ------------------------------------------------------ |
| `openai`            | `OPENAI_API_KEY`                   | Standard OpenAI, any OpenAI-compatible local server    |
| `anthropic`         | `ANTHROPIC_API_KEY`                | Anthropic API with prompt caching on system prompts    |
| `azure_openai`      | `AZURE_API_KEY` + `AZURE_ENDPOINT` | BAA-eligible Azure OpenAI (key for healthcare/finance) |
| `ollama`            | None                               | Fully air-gapped deployments; no data leaves the host  |
| `openai_compatible` | Optional key                       | vLLM, Together, Groq, any OpenAI-spec endpoint         |

The `LLMClient` in `core/llm/client.py` ports Odysseus's provider detection and quirk-handling logic unchanged. This includes Anthropic prompt caching, Ollama JSON-mode normalization, and dead-host cooldown.

---

## 9. Auth & Multi-Tenancy

### API key structure

```
drapi_live_<org_prefix>_<32_byte_hex>
└─ prefix indicates environment (live vs test)
   org_prefix is first 8 chars of org_id (for routing, not auth)
   32-byte hex is the secret
```

On issue: full key returned once to customer, never stored. DB stores `bcrypt(key)` + org association. On each request, the middleware hashes the presented key and compares to stored hash.

Key scopes:

- `research:write` — submit jobs
- `research:read` — read results and audit own jobs
- `admin` — org management, all audit logs, usage export

### Multi-tenancy isolation

Every DB query is scoped to `org_id`. No cross-org data access is possible at the application layer. PostgreSQL row-level security (RLS) is enabled as a defence-in-depth layer — even if application code has a bug, a query from org A cannot return org B's rows.

```sql
ALTER TABLE research_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON research_jobs
  USING (org_id = current_setting('app.current_org_id'));
```

The API middleware sets `SET LOCAL app.current_org_id = '<org_id>'` at the start of every transaction.

---

## 10. Deployment Topology

### Docker Compose (standard enterprise deploy)

```yaml
# deploy/docker-compose.yml
services:
  api:
    image: deep-research-api:latest
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:${PG_PASSWORD}@postgres/drapi
      REDIS_URL: redis://redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
    depends_on: [postgres, redis]

  worker:
    image: deep-research-api:latest
    command: python -m arq core.queue.worker.WorkerSettings
    environment: *api-env
    deploy:
      replicas: 2           # scale up for higher throughput

  admin:
    image: deep-research-api:latest
    command: uvicorn admin.app:app --port 8001
    ports: ["127.0.0.1:8001:8001"]   # internal only
    environment: *api-env

  postgres:
    image: postgres:16-alpine
    volumes: ["pgdata:/var/lib/postgresql/data"]
    environment:
      POSTGRES_DB: drapi
      POSTGRES_PASSWORD: ${PG_PASSWORD}

  redis:
    image: redis:7-alpine
    volumes: ["redisdata:/data"]
    command: redis-server --appendonly yes

  searxng:
    image: searxng/searxng:latest    # optional: local search, no external API needed
    volumes: ["./searxng:/etc/searxng"]
```

### Air-gap variant additions

```yaml
# deploy/docker-compose.airgap.yml additions
ollama:
  image: ollama/ollama:latest
  volumes: ["ollamadata:/root/.ollama"]
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

In the air-gap config, `searxng` handles all search (no Brave/Tavily), and Ollama handles all LLM calls. Zero bytes leave the customer's network.

---

## 11. What You Strip from Odysseus

To build this product, you extract the following from Odysseus and discard everything else:

### Keep (port directly)

| Odysseus module                        | Maps to                                         |
| -------------------------------------- | ----------------------------------------------- |
| `src/deep_research.py`                 | `core/research/engine.py` + subdirectory        |
| `src/llm_core.py`                      | `core/llm/client.py` + `providers/`             |
| `src/prompt_security.py`               | `core/llm/prompt_security.py` (unchanged)       |
| `src/model_context.py`                 | `core/llm/context_sizing.py` (unchanged)        |
| `src/visual_report.py` (HTML renderer) | Adapt to `core/export/` (add DOCX/PDF variants) |
| `core/auth.py` (API key patterns)      | `core/security/api_keys.py` (strip session/2FA) |
| `core/database.py` (Fernet patterns)   | `core/security/encryption.py`                   |
| `integrations/searxng.py`              | `integrations/searxng.py` (unchanged)           |
| `integrations/brave.py`                | `integrations/brave.py` (unchanged)             |
| `src/context_compactor.py`             | Inside `core/llm/client.py`                     |

### Discard entirely

- `src/agent_loop.py` — chat agent, not needed
- `src/task_scheduler.py` — replaced by ARQ
- `src/teacher_escalation.py` — skills system, not needed for v1
- `src/memory.py` — personal memory, not relevant
- `src/tool_implementations.py` — all 4,145 lines
- `routes/` — all 48 route files (replaced by `api/routes/`)
- `routes/cookbook_routes.py` — LLM serving management, customer brings their own
- `routes/email_routes.py` — not needed
- `static/` — entire frontend
- `services/memory/` — skills system
- `mcp_servers/` — not needed for v1
- `companion/` — mobile pairing

The result is approximately **30% of the Odysseus codebase**, focused entirely on the research pipeline.

---

## 12. Build Sequence

### Week 1–2: Core pipeline

- Port `deep_research.py` → `core/research/engine.py` with progress callbacks and cancellation
- Port `llm_core.py` → `core/llm/` with provider modules
- Write `db/models/` — all tables, Alembic setup
- `POST /v1/research` → enqueue → worker executes → write result

### Week 3: API surface + auth

- API key issuance, bcrypt hashing, middleware
- `GET /v1/research/{id}` polling endpoint
- Per-org LLM backend configuration
- Audit log middleware (every request)

### Week 4: Exports + webhooks

- DOCX export via `python-docx` with sources table
- PDF export via WeasyPrint
- Webhook dispatcher with HMAC signing and Redis retry queue
- `GET /v1/reports/{id}/export`

### Week 5: Admin dashboard + hardening

- Starlette admin: job monitor, audit viewer, usage export
- Rate limiting (Redis sliding window)
- PostgreSQL RLS policies
- Docker Compose + air-gap compose variant

### Week 6: Testing + docs

- Unit tests for planner, synthesizer, export, auth
- Integration tests for full research endpoint
- OpenAPI spec (`docs/openapi.yaml`)
- Security doc (`docs/security.md`) — the one-pager Legal needs

### First customer milestone

At the end of week 6 you have: a Docker Compose stack, a REST API that accepts a query and returns a cited report, DOCX export, full audit logging, and a security doc. That is sufficient for a Pilot conversation with a pharma competitive intelligence team.

---

_All module paths reference the structure in Section 2. All Odysseus references cite the analysis document from session context._
