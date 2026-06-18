<div align="center">

# Vanta

**Self-Hosted, Privacy-First Research-as-a-Service**

*A multi-agent deep research engine that runs entirely inside your infrastructure*

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-6366f1?style=flat-square)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/avirooppal/Vanta-Deep-Research-API/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/avirooppal/Vanta-Deep-Research-API/actions)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/compose/)

</div>

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Key Features](#key-features)
3. [High-Level Architecture](#high-level-architecture)
4. [System Components](#system-components)
5. [The Multi-Agent Pipeline](#the-multi-agent-pipeline)
6. [Detailed Workflow Analysis](#detailed-workflow-analysis)
   - [Job Submission Flow](#1-job-submission-flow)
   - [Worker Execution Flow](#2-worker-execution-flow)
   - [Research Engine Loop](#3-research-engine-loop)
   - [Webhook Delivery Flow](#4-webhook-delivery-flow)
   - [Report Export Flow](#5-report-export-flow)
   - [Error Handling Flow](#6-error-handling-flow)
7. [Sequence Diagrams](#sequence-diagrams)
8. [Data Flow Architecture](#data-flow-architecture)
9. [Directory Structure](#directory-structure)
10. [Technology Stack](#technology-stack)
11. [API Documentation](#api-documentation)
12. [Database Design](#database-design)
13. [Configuration](#configuration)
14. [Installation](#installation)
    - [Prerequisites](#prerequisites)
    - [Docker Setup (Recommended)](#docker-setup-recommended)
    - [Local Development Setup](#local-development-setup)
    - [Air-Gap / Fully Offline Setup](#air-gap--fully-offline-setup)
    - [Verification](#verification)
15. [Developer CLI](#developer-cli)
16. [Development Workflow](#development-workflow)
17. [Testing Strategy](#testing-strategy)
18. [Security Architecture](#security-architecture)
19. [Observability](#observability)
20. [Deployment Architecture](#deployment-architecture)
21. [CI/CD Pipeline](#cicd-pipeline)
22. [Performance Considerations](#performance-considerations)
23. [Failure Handling](#failure-handling)
24. [Troubleshooting Guide](#troubleshooting-guide)
25. [FAQ](#faq)
26. [Roadmap](#roadmap)
27. [Contributing](#contributing)
28. [License](#license)
29. [Appendix](#appendix)

---

## Executive Summary

Vanta is a **headless, API-first Research-as-a-Service** platform designed for enterprise deployment inside customer VPCs, air-gapped networks, and on-premises infrastructure.

Given a natural language query, Vanta autonomously executes a **multi-round, multi-agent research loop** — decomposing the question, searching the web, fetching and validating sources, extracting structured facts, detecting contradictions, and synthesizing a comprehensive, citation-backed report in Markdown, PDF, or JSON — entirely inside the customer's own perimeter.

### Who It Is For

| Audience | Use Case |
|---|---|
| **Security & compliance teams** | Run deep investigations without data leaving the network |
| **Enterprise analysts** | Automate competitive intelligence, market research, and due diligence |
| **Platform engineers** | Embed research as a background capability into existing SaaS products |
| **Data teams** | Build a compounding knowledge graph from prior research sessions |
| **DevOps / MLOps** | Trigger research jobs from CI/CD pipelines, Zapier, or n8n |

### Why It Exists

- Standard LLMs hallucinate. Vanta runs a **structured evidence pipeline**: every claim in a report is traceable to a fetched, validated, LLM-scored source.
- Cloud research APIs send your proprietary queries to third parties. Vanta runs entirely in your network — the only external calls are to the LLM provider and search engine of *your choosing*.
- Multi-round iteration means Vanta identifies and fills knowledge gaps that a single-shot prompt would miss.

---

## Key Features

| Feature | Description | Status |
|---|---|---|
| **Multi-Agent Pipeline** | 7-agent loop: Coordinator → Search → Validator → Extractor → Contradiction → Synthesizer → CitationVerifier | ✅ Stable |
| **Bring Your Own Key (BYOK)** | Pass `sk-...`, `sk-ant-...`, `AIza...`, or `sk-or-...` keys as Bearer token; provider auto-detected | ✅ Stable |
| **Persistent Knowledge Graph** | Extracted claims embedded with pgvector; searchable across all past sessions | ✅ Stable |
| **Server-Sent Events (SSE)** | Stream live progress (percent, source count, status) to any client | ✅ Stable |
| **Multi-Format Export** | Export reports as Markdown, JSON, or PDF (via WeasyPrint) | ✅ Stable |
| **Chat with Report** | Post-completion conversational Q&A grounded in the generated report | ✅ Stable |
| **Global Knowledge Search** | Vector similarity search across all prior research sessions | ✅ Stable |
| **HMAC-Signed Webhooks** | Asynchronous delivery with replay protection and 5-attempt exponential backoff | ✅ Stable |
| **Contradiction Detection** | Dedicated agent surfaces conflicting facts with severity ratings and resolution suggestions | ✅ Stable |
| **Trust Scoring** | Hybrid heuristic + LLM scoring per source; low-trust sources (< 30/100) are discarded | ✅ Stable |
| **Cancellation** | `DELETE /v1/research/{id}` cleanly aborts a running job mid-loop | ✅ Stable |
| **Prometheus Metrics** | `/metrics` endpoint exposing FastAPI instrumentation out of the box | ✅ Stable |
| **Self-Hosted Search** | SearXNG as the default search provider — no Brave/Tavily API key required | ✅ Stable |
| **Air-Gap Mode** | Swap search for SearXNG + swap LLM for Ollama for zero external network calls | ✅ Stable |
| **Playwright Fetching** | JavaScript-rendered pages fetched via Playwright headless Chromium | ✅ Stable |
| **Plugin Extensibility** | Drop in custom `BaseSearchPlugin` / `BaseExtractorPlugin` via `core/plugins/registry.py` | 🚧 Beta |

---

## High-Level Architecture

Vanta is a **Queue-Based Modular Monolith** with four process types communicating through two shared data stores.

```mermaid
flowchart TD
    Client(["Client<br/>(curl / SDK / n8n / CI)"])

    subgraph Network["Customer Network Boundary"]
        subgraph Services["Application Processes"]
            API["API Server<br/>FastAPI :8000"]
            Worker["ARQ Worker<br/>(job executor)"]
        end

        subgraph Data["Shared Data Stores"]
            PG[("PostgreSQL 16<br/>+ pgvector<br/>(jobs, reports, claims,<br/>sources, audit, webhooks)")]
            Redis[("Redis 7<br/>(job queue,<br/>webhook retry queue)")]
        end

        subgraph Optional["Optional Local Services"]
            SearXNG["SearXNG :8085<br/>(self-hosted search)"]
            Caddy["Caddy :80/:443<br/>(TLS reverse proxy)"]
            Ollama["Ollama :11434<br/>(local LLM — air-gap)"]
        end
    end

    subgraph External["External (Optional — Customer Chooses)"]
        LLM["LLM Provider<br/>(OpenAI / Anthropic /<br/>Gemini / OpenRouter)"]
        Search["Search API<br/>(Brave / Tavily)"]
    end

    Client -- "POST /v1/research<br/>Authorization: Bearer sk-..." --> Caddy
    Caddy --> API
    API -- "enqueue job" --> Redis
    API -- "write ResearchJob row" --> PG
    Redis -- "task dispatch" --> Worker
    Worker -- "read/write job, report,<br/>sources, claims, usage" --> PG
    Worker -- "search queries" --> SearXNG
    Worker -- "LLM calls" --> LLM
    Worker -- "webhook retry queue" --> Redis
    SearXNG -- "fallback" --> Search
```

### Architectural Principles

| Principle | Implementation |
|---|---|
| **Stateless API layer** | API servers carry zero in-memory state; scale horizontally behind any load balancer |
| **Async-first** | Every I/O operation (DB, HTTP, LLM) is `async/await`; `asyncio.Semaphore` gates concurrent URL fetches |
| **Incremental persistence** | Sources and claims are written to DB after each round, not just at job completion — polling gives live partial results |
| **Provider abstraction** | `LLMClient` encapsulates all provider quirks; engine code is provider-agnostic |
| **Privacy by design** | Fetched page content lives in memory only during job execution; it is never written to disk or logs |

---

## System Components

```mermaid
graph LR
    subgraph API["api/ — HTTP Layer"]
        App["app.py<br/>FastAPI entrypoint"]
        Auth["middleware/auth.py<br/>BYOK detection"]
        AuditMW["middleware/audit_log.py<br/>Immutable request log"]
        R1["routes/research.py<br/>Submit / Poll / Stream / Cancel / Chat"]
        R2["routes/reports.py<br/>Export (md / json / pdf)"]
        R3["routes/sources.py<br/>Source listing"]
        R4["routes/webhooks.py<br/>CRUD webhook endpoints"]
        R5["routes/health.py<br/>Liveness / Readiness"]
    end

    subgraph Core["core/ — Business Logic"]
        Engine["research/engine.py<br/>IterResearch orchestrator"]
        Agents["research/agents/<br/>7-agent system"]
        Memory["research/memory.py<br/>pgvector MemoryStore"]
        LLM["llm/client.py<br/>Unified LLMClient"]
        Queue["queue/tasks.py<br/>ARQ task runner"]
        Webhooks["webhooks/dispatcher.py<br/>HMAC-signed delivery"]
        Security["security/<br/>Fernet encryption"]
    end

    subgraph DB["db/ — Persistence"]
        Models["models/<br/>ResearchJob, Report,<br/>Source, Claim, UsageRecord,<br/>WebhookEndpoint, AuditLog"]
        Migrations["migrations/<br/>Alembic async"]
    end

    subgraph Integrations["integrations/ — External Adapters"]
        SearXNGInt["searxng.py<br/>REST client"]
        Fetcher["fetcher.py<br/>httpx + BS4 HTML stripper"]
    end

    App --> Auth --> R1 & R2 & R3 & R4 & R5
    App --> AuditMW
    R1 --> Queue
    Queue --> Engine
    Engine --> Agents --> Memory & LLM & SearXNGInt & Fetcher
    Queue --> Webhooks
    Agents --> DB
```

### Component Responsibility Table

| Component | Owns | Inputs | Outputs |
|---|---|---|---|
| `api/app.py` | Application bootstrap, middleware chain, lifespan | HTTP requests | Routed responses |
| `api/middleware/auth.py` | BYOK key parsing, provider auto-detection | `Authorization` header | `request.state.transient_backend` dict |
| `api/middleware/audit_log.py` | Append-only request log | Every HTTP request | `AuditLog` rows |
| `api/routes/research.py` | Job lifecycle: submit, poll, stream, cancel, chat | HTTP, `request.state` | `ResearchJob` record + ARQ task |
| `core/research/engine.py` | IterResearch orchestration loop | Query string, LLMClient | `ReportOutput` |
| `core/research/agents/` | Individual agent reasoning | `ResearchState` | Decisions, findings, contradictions, report |
| `core/research/memory.py` | pgvector knowledge graph read/write | Claim text, embeddings | Semantically similar past claims |
| `core/llm/client.py` | Provider routing, token tracking | `LLMConfig`, messages | `LLMResponse` |
| `core/queue/tasks.py` | ARQ task bodies; orchestrates engine → DB → webhook | `job_id` string | Completed `Report`, `UsageRecord`, webhook events |
| `core/webhooks/dispatcher.py` | HMAC signing, webhook delivery queueing | `job_id`, event type | ARQ `deliver_webhook_job` tasks |
| `db/models/` | SQLAlchemy ORM definitions | — | Table schemas for Alembic migrations |
| `integrations/searxng.py` | SearXNG search REST calls | Query string | List of URLs + snippets |
| `integrations/fetcher.py` | Async HTTP fetch + HTML-to-text | URL | Plain text page content |

---

## The Multi-Agent Pipeline

Vanta's core is a **7-agent sequential pipeline** instantiated fresh per research job. All agents receive the same shared `ResearchState` object and communicate through an in-memory message bus.

```mermaid
flowchart TD
    Start(["POST /v1/research<br/>job queued"])
    C["🎯 CoordinatorAgent<br/>Decides: CONTINUE or SYNTHESIZE<br/>based on round count & findings quality"]
    S["🔍 SearchAgent<br/>Generates semantic + keyword sub-queries<br/>to fill knowledge gaps"]
    SX["SearXNG / Brave / Tavily<br/>Returns URLs + snippets"]
    V["✅ ValidatorAgent<br/>Assigns trust_score 0–100<br/>Flags: paywalled, opinion, low-quality"]
    E["⛏️ ExtractorAgent<br/>Pulls structured Claim objects<br/>Checks for overlap with MemoryStore"]
    PG[("PostgreSQL<br/>Source + Claim rows written<br/>after each round")]
    CON["⚡ ContradictionAgent<br/>Scans all findings for conflicts<br/>Assigns severity + resolution_suggestion"]
    SYN["📝 SynthesizerAgent<br/>Compiles full Markdown report<br/>Injects citation markers inline"]
    CIT["📎 CitationVerifierAgent<br/>Validates [1], [2] markers<br/>Fixes broken citation references"]
    End(["ReportOutput returned<br/>to ARQ worker"])

    Start --> C
    C -- "CONTINUE" --> S
    S --> SX
    SX --> V
    V -- "trust_score ≥ 30" --> E
    V -- "trust_score < 30" --> discard["🗑️ Discarded"]
    E --> PG
    E --> CON
    CON --> C
    C -- "SYNTHESIZE" --> SYN
    SYN --> CIT
    CIT --> End
```

### Agent Specifications

| Agent | File | Role | Key Decision |
|---|---|---|---|
| **CoordinatorAgent** | `agents/coordinator.py` | Orchestration control loop | `CONTINUE` vs `SYNTHESIZE` — uses LLM when findings exist, rule-based when round limit reached |
| **SearchAgent** | `agents/search.py` | Query generation | Generates multiple semantic and keyword sub-queries targeting knowledge gaps |
| **ValidatorAgent** | `agents/validator.py` | Source quality gate | Assigns `trust_score` 0–100; sources below 30 are dropped before extraction |
| **ExtractorAgent** | `agents/extractor.py` | Structured fact extraction | Extracts `Finding` objects; cross-references `MemoryStore` to avoid duplicate claims |
| **ContradictionAgent** | `agents/contradiction.py` | Conflict detection | Compares all findings; produces `Contradiction` objects with severity (`low`/`medium`/`high`) and resolution suggestions |
| **SynthesizerAgent** | `agents/synthesizer.py` | Report generation | Merges all findings into a structured Markdown report with inline `[1]`, `[2]` citations |
| **CitationVerifierAgent** | `agents/citation_verifier.py` | Citation integrity | Validates and repairs inline citation markers to prevent hallucinated references |

---

## Detailed Workflow Analysis

### 1. Job Submission Flow

A client POSTs to `/v1/research`. The API server validates the request, persists a job record, and enqueues it — returning a `202 Accepted` before any LLM call is made.

```mermaid
flowchart LR
    Client --> Auth["auth_middleware\nDetect provider from key prefix\nsk-... → openai\nsk-ant-... → anthropic\nAIza... → gemini (openai_compatible)\nsk-or-... → openrouter"]
    Auth --> Audit["audit_log_middleware\nWrite AuditLog row (append-only)"]
    Audit --> Route["POST /v1/research\nValidate request body\nClamp max_rounds (1–5)\nClamp priority (1–5)"]
    Route --> Encrypt["Fernet-encrypt API key\nStore in metadata_json JSONB"]
    Encrypt --> DB[("PostgreSQL\nINSERT research_jobs\nstatus='queued'")]
    DB --> ARQ["ARQ\nenqueue_job('run_research_job', job_id)"]
    ARQ --> Response["202 Accepted\n{id, status, query, created_at}"]
```

**Step-by-step:**
1. Request arrives; `auth_middleware` reads `Authorization: Bearer <key>` and auto-detects LLM provider from key prefix.
2. `audit_log_middleware` writes an immutable `AuditLog` row (method, path, IP, user-agent, timestamp).
3. Route handler creates a `ResearchJob` row in PostgreSQL with `status='queued'`.
4. If the request body includes BYOK credentials, the API key is Fernet-encrypted and stored in the job's `metadata_json` column.
5. An ARQ task `run_research_job` is enqueued to Redis with the `job_id` as payload.
6. The handler returns `202 Accepted` immediately. The client can now poll `GET /v1/research/{id}` or open an SSE stream.

**Failure scenarios:**

| Failure | HTTP Status | Behaviour |
|---|---|---|
| Missing `Authorization` header | `401` | Middleware rejects before route runs |
| Unrecognizable key prefix, no `X-Provider` header | `401` | Middleware rejects with detection instructions |
| Invalid `max_rounds` or `priority` | Silent clamp | `max_rounds` clamped to 1–5, `priority` clamped to 1–5 |
| Redis unavailable at enqueue time | `500` | Job row already committed; retry logic should re-enqueue |

---

### 2. Worker Execution Flow

The ARQ worker picks up the job from Redis, decrypts the LLM credentials, initializes the engine, and drives the entire research loop.

```mermaid
flowchart TD
    Redis["Redis\n(ARQ queue)"] --> Worker["ARQ Worker\nrun_research_job(ctx, job_id)"]
    Worker --> Load["Load ResearchJob from PostgreSQL\nUpdate status = 'running'\nSet started_at = now()"]
    Load --> Decrypt["Decrypt Fernet-encrypted api_key\nfrom metadata_json\nBuild LLMClient with provider config"]
    Decrypt --> Engine["core.research.engine.run_research()"]
    Engine --> Report["ReportOutput returned"]
    Report --> Persist["INSERT Report\nINSERT UsageRecord\nUPDATE job.status = 'completed'\nUPDATE job.progress_pct = 100"]
    Persist --> Webhook["fire_webhook(job_id, 'research.completed')"]
    Webhook --> Done["Done ✓"]

    Decrypt -- "api_key missing" --> Fail["UPDATE job.status = 'failed'\njob.error = 'No LLM backend configured'"]
    Engine -- "exception raised" --> ErrPersist["UPDATE job.status = 'failed'\nUPDATE job.error = str(exc)\nINSERT UsageRecord (partial)"]
    ErrPersist --> ErrWebhook["fire_webhook(job_id, 'research.failed')"]
```

**Incremental writes:** The `on_progress` callback fires after every round, writing new `Source` and `Claim` rows to PostgreSQL and updating `job.progress_pct`. Clients can observe partial results via `GET /v1/research/{id}` without waiting for the job to complete.

---

### 3. Research Engine Loop

`core/research/engine.py` is the orchestration core. It runs the 7-agent pipeline in a `while not state.is_done` loop.

```mermaid
flowchart TD
    Start(["run_research(question, llm, searxng_url, max_rounds)"])
    State["Initialize ResearchState\nInstantiate all 7 agents\nCreate MemoryStore (pgvector)"]
    Cancelled{"cancelled.is_set()?\n(DELETE /v1/research/{id})"}
    Coord["CoordinatorAgent.run(state)\nDecide CONTINUE or SYNTHESIZE"]
    Search["SearchAgent.run(state)\nGenerate sub-queries"]
    Fetch["search_searxng(queries) → URLs\nfetch_url(urls) via asyncio.Semaphore(3)\nPlaywright headless Chromium"]
    Validate["ValidatorAgent.run(page)\ntrust_score = heuristic + LLM\nDrop if trust_score < 30"]
    Extract["ExtractorAgent.run(validated_source, question, round, memory)\nExtract Finding objects\nEmbed + store in pgvector via MemoryStore"]
    Contra["ContradictionAgent.run(state)\nScan findings for conflicts"]
    Progress["on_progress(RoundResult)\n→ writes Source + Claim rows to DB\n→ updates job.progress_pct"]
    Synthesize["SynthesizerAgent.run(state)\nWrite full Markdown report\nPrioritize recent-round findings\nContext-window-aware truncation"]
    CitationVerify["CitationVerifierAgent.run(state, report)\nValidate [1], [2] markers\nRepair broken references"]
    Return(["Return ReportOutput to worker"])

    Start --> State --> Cancelled
    Cancelled -- "yes" --> Return
    Cancelled -- "no" --> Coord
    Coord -- "SYNTHESIZE" --> Synthesize
    Coord -- "CONTINUE" --> Search
    Search --> Fetch --> Validate --> Extract --> Contra --> Progress
    Progress --> Cancelled
    Synthesize --> CitationVerify --> Return
```

**Concurrency model:** URL fetching is bounded by `asyncio.Semaphore(settings.extraction_concurrency)` (default 3). Up to 15 URLs are processed per round. Each fetch → validate → extract pipeline runs concurrently within this bound.

---

### 4. Webhook Delivery Flow

```mermaid
flowchart LR
    Worker["ARQ Worker\n(job completed/failed)"] --> Dispatcher["webhooks/dispatcher.py\nfire_webhook(job_id, event)"]
    Dispatcher --> LoadWebhooks["SELECT active WebhookEndpoints"]
    LoadWebhooks --> Sign["Fernet-decrypt endpoint secret\nhmac_sign(payload, timestamp, secret)\nHeader: X-Webhook-Signature\nHeader: X-Webhook-Timestamp (replay protection)"]
    Sign --> Enqueue["ARQ enqueue_job('deliver_webhook_job'\nurl, payload, signature, timestamp, attempt=1)"]
    Enqueue --> Deliver["deliver_webhook_job\nHTTP POST to customer endpoint\n10s timeout"]
    Deliver -- "2xx" --> Success["✓ Delivered"]
    Deliver -- "5xx / timeout (attempt < 5)" --> Retry["Re-enqueue with _defer_by:\n10s → 30s → 120s → 600s → 3600s"]
    Deliver -- "5xx / timeout (attempt = 5)" --> Dead["LOG error: permanent failure"]
```

**HMAC signature format:**

```
X-Webhook-Signature: t=<unix_timestamp>,v1=<sha256_hex>
```

The signature is computed as `HMAC-SHA256(payload_json + timestamp, endpoint_secret)`. Consumers should verify both the signature and that `|now() - t| < 300` seconds to prevent replay attacks.

---

### 5. Report Export Flow

```mermaid
flowchart LR
    Client --> ExportRoute["GET /v1/reports/{id}/export?format=md|json|pdf"]
    ExportRoute --> LoadReport["db.get(Report, report_id)"]
    LoadReport -- "format=md" --> MD["PlainTextResponse\nContent-Disposition: attachment\nmedia_type: text/markdown"]
    LoadReport -- "format=json" --> JSON["JSONResponse\n{id, summary, body_md, citations[]}"]
    LoadReport -- "format=pdf" --> PDF["markdown2.markdown(content_md)\nHTML(string=html).write_pdf()\nResponse(application/pdf)"]
    LoadReport -- "not found" --> 404["404 Not Found"]
    PDF -- "import error" --> 500["500: PDF dependencies not installed"]
```

---

### 6. Error Handling Flow

```mermaid
stateDiagram-v2
    [*] --> queued : POST /v1/research (202 Accepted)
    queued --> running : Worker picks up ARQ task
    running --> completed : Engine returns ReportOutput
    running --> failed : Exception raised in engine
    running --> cancelled : DELETE /v1/research/{id}\ncancel_event.set()
    completed --> [*] : Webhook fired (research.completed)
    failed --> [*] : Webhook fired (research.failed)\nUsageRecord written (partial)
    cancelled --> [*] : job.finished_at set
```

---

## Sequence Diagrams

### Full Research Job Lifecycle

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI API
    participant R as Redis (ARQ Queue)
    participant W as ARQ Worker
    participant DB as PostgreSQL
    participant LLM as LLM Provider
    participant SX as SearXNG

    C->>API: POST /v1/research {query, max_rounds}
    Note over API: auth_middleware: detect provider from Bearer key
    Note over API: audit_log_middleware: write AuditLog row
    API->>DB: INSERT research_jobs (status='queued')
    API->>R: enqueue_job('run_research_job', job_id)
    API-->>C: 202 Accepted {job_id, status='queued'}

    C->>API: GET /v1/research/{id}/stream (SSE)
    Note over C,API: Client opens SSE connection for live progress

    R->>W: Dequeue run_research_job(job_id)
    W->>DB: UPDATE status='running', started_at=now()
    W->>DB: SELECT metadata_json → decrypt api_key

    loop For each research round (up to max_rounds)
        W->>LLM: CoordinatorAgent → CONTINUE or SYNTHESIZE?
        W->>LLM: SearchAgent → generate sub-queries
        W->>SX: search_searxng(queries) → URLs
        W->>LLM: ValidatorAgent → trust_score per source
        W->>LLM: ExtractorAgent → extract findings
        W->>DB: INSERT Source rows (partial results visible)
        W->>DB: INSERT Claim rows with embedding vectors
        W->>DB: UPDATE job.progress_pct
        API-->>C: SSE event: {progress_pct, source_count, status}
        W->>LLM: ContradictionAgent → detect conflicts
    end

    W->>LLM: SynthesizerAgent → compile Markdown report
    W->>LLM: CitationVerifierAgent → validate citations
    W->>DB: INSERT Report, INSERT UsageRecord
    W->>DB: UPDATE job.status='completed', progress_pct=100
    API-->>C: SSE event: {status='completed', progress_pct=100}

    W->>R: enqueue_job('deliver_webhook_job', url, payload, sig)
    R->>W: Dequeue deliver_webhook_job
    W-->>ExternalSystem: POST /callback {event, job_id, report_url}

    C->>API: GET /v1/research/{id}
    API->>DB: SELECT ResearchJob + Report + Sources
    API-->>C: 200 {status, report: {summary, body_md, citations[]}}
```

### Webhook Retry Sequence

```mermaid
sequenceDiagram
    participant W as ARQ Worker
    participant R as Redis
    participant EP as Customer Endpoint

    W->>R: enqueue deliver_webhook_job (attempt=1)
    R->>W: Dequeue
    W->>EP: POST (attempt 1)
    EP-->>W: 503 Service Unavailable
    W->>R: Re-enqueue, _defer_by=10s (attempt=2)
    R->>W: Dequeue (after 10s)
    W->>EP: POST (attempt 2)
    EP-->>W: 500 Internal Server Error
    W->>R: Re-enqueue, _defer_by=30s (attempt=3)
    R->>W: Dequeue (after 30s)
    W->>EP: POST (attempt 3)
    EP-->>W: 200 OK
    Note over W: Delivered ✓
```

---

## Data Flow Architecture

### Ingestion Pipeline

```mermaid
flowchart LR
    Q["Natural Language Query"] --> Planner["SearchAgent\nDecomposes into N sub-queries"]
    Planner --> SearXNG["SearXNG\nReturns URLs + snippets"]
    SearXNG --> Fetcher["integrations/fetcher.py\nhttpx AsyncClient\nPlaywright (JS-heavy pages)\nBS4 HTML stripping"]
    Fetcher --> Validator["ValidatorAgent\ntrust_score = f(domain_heuristics, LLM_score)\nFlags: paywalled, opinion, low-quality"]
    Validator --> Extractor["ExtractorAgent\nLLM call: extract Finding list\nCross-ref with MemoryStore"]
```

### Storage Architecture

```mermaid
flowchart TD
    subgraph Hot["Hot Path (per-job)"]
        RJ["research_jobs\nPrimary job record\nstatus, progress_pct, metadata_json"]
        SRC["sources\nURL, title, excerpt\nround_number, trust_score, flags"]
        CLM["claims\nfact (text)\nembedding (vector 1536)\ntrust_score\ncontradicts_claim_id"]
        RPT["reports\nsummary, content_md\ncontent_json (citations JSONB)"]
        USG["usage_records\ntokens_in, tokens_out\nsources_fetched, duration_seconds"]
    end

    subgraph Persistent["Persistent / Config"]
        WH["webhook_endpoints\nurl, secret (Fernet-encrypted)\nis_active"]
        AL["audit_log\nAppend-only\nmethod, path, query_text\nip_address, duration_ms"]
    end

    RJ --> SRC
    RJ --> CLM
    RJ --> RPT
    RJ --> USG
```

### Knowledge Graph (pgvector)

Every extracted claim is embedded (1536-dim, OpenAI `text-embedding-3-small`) and stored in the `claims` table with a pgvector `Vector(1536)` column. This enables:

- **Per-job memory:** `MemoryStore.search_memory(topic)` finds semantically similar claims within the same job, preventing duplicate extraction.
- **Global knowledge search:** `GET /v1/knowledge-graph/search?q=...` performs cosine similarity search across **all** past research sessions.

```sql
-- Per-job semantic search
SELECT * FROM claims
WHERE job_id = $1
ORDER BY embedding <=> $2  -- cosine distance
LIMIT 5;

-- Global cross-session search
SELECT * FROM claims
ORDER BY embedding <=> $1
LIMIT 10;
```

---

## Directory Structure

```text
deep-research-api/                     # Project root
│
├── api/                               # FastAPI HTTP layer
│   ├── app.py                         # Entrypoint: lifespan, middleware chain, router mount
│   ├── middleware/
│   │   ├── auth.py                    # BYOK detection + transient_backend injection
│   │   └── audit_log.py              # Append-only audit logger
│   ├── routes/
│   │   ├── research.py               # POST /research, GET /research/{id}, SSE, DELETE, chat
│   │   ├── reports.py                # GET /reports/{id}/export (md | json | pdf)
│   │   ├── sources.py                # GET /research/{id}/sources
│   │   ├── webhooks.py               # POST/GET/DELETE /webhooks
│   │   └── health.py                 # GET /health, /health/ready, /health/live
│   └── static/
│       └── index.html                # Built-in debugging console UI
│
├── core/                              # Business logic (framework-agnostic)
│   ├── config.py                      # Pydantic Settings (env-var driven)
│   ├── logging.py                     # Structured logging + request_id context var
│   ├── research/
│   │   ├── engine.py                  # IterResearch orchestrator loop
│   │   ├── state.py                   # ResearchState, Finding, ValidatedSource, Contradiction
│   │   ├── memory.py                  # MemoryStore: pgvector read/write
│   │   └── agents/
│   │       ├── base.py                # BaseAgent: LLM + in-memory message bus publish
│   │       ├── message_bus.py         # Simple in-process pub/sub event bus
│   │       ├── coordinator.py         # CoordinatorAgent: CONTINUE / SYNTHESIZE
│   │       ├── search.py              # SearchAgent: sub-query generation
│   │       ├── validator.py           # ValidatorAgent: trust scoring
│   │       ├── extractor.py           # ExtractorAgent: fact extraction
│   │       ├── contradiction.py       # ContradictionAgent: conflict detection
│   │       ├── synthesizer.py         # SynthesizerAgent: Markdown report
│   │       ├── citation_verifier.py   # CitationVerifierAgent: citation repair
│   │       └── tools.py               # Shared LLM tool/function call helpers
│   ├── llm/
│   │   ├── client.py                  # LLMClient: routing, token tracking, embedding
│   │   ├── types.py                   # LLMConfig, Message, LLMResponse dataclasses
│   │   └── providers/
│   │       ├── openai.py              # OpenAI / Azure / OpenRouter / Ollama / Gemini
│   │       └── anthropic.py           # Anthropic native (prompt caching)
│   ├── queue/
│   │   ├── worker.py                  # ARQ WorkerSettings + Redis settings
│   │   └── tasks.py                   # run_research_job, deliver_webhook_job, cleanup_audit_log
│   ├── webhooks/
│   │   ├── dispatcher.py              # fire_webhook: load endpoints, sign, enqueue
│   │   └── signing.py                 # HMAC-SHA256 signing utility
│   ├── security/
│   │   ├── encryption.py              # Fernet encrypt/decrypt for secrets at rest
│   │   └── api_keys.py                # Key generation and hashing utilities
│   └── plugins/
│       └── registry.py                # Dynamic plugin registry for custom search/extract
│
├── db/                                # Database layer
│   ├── engine.py                      # SQLAlchemy async engine + Base declarative
│   ├── session.py                     # AsyncSession context manager
│   └── models/
│       ├── research_job.py            # ResearchJob table
│       ├── report.py                  # Report table (markdown + JSONB citations)
│       ├── source.py                  # Source table (URL, excerpt, trust_score)
│       ├── claim.py                   # Claim table (fact, pgvector embedding)
│       ├── usage_record.py            # UsageRecord (tokens, duration, source count)
│       ├── webhook.py                 # WebhookEndpoint (url, Fernet-encrypted secret)
│       └── audit_log.py              # AuditLog (immutable, append-only)
│
├── integrations/                      # External adapter layer
│   ├── searxng.py                     # SearXNG REST client (returns URL + snippet list)
│   └── fetcher.py                     # httpx + BeautifulSoup HTML-to-text converter
│
├── frontend/                          # Product landing page (Vite + React + TypeScript)
│   └── src/
│       ├── App.tsx                    # Landing page: hero, feature cards, code blocks
│       └── components/ui/             # Button, etc.
│
├── tests/
│   ├── unit/                          # Pure unit tests (no real DB/Redis)
│   │   └── test_sources.py
│   ├── integration/                   # FastAPI TestClient against mocked dependencies
│   │   └── test_research_submit.py
│   └── e2e/                           # End-to-end (requires live stack)
│
├── deploy/
│   ├── Dockerfile                     # Multi-stage: builder + slim runtime (Python 3.12)
│   ├── docker-compose.yml             # Full stack: API + Worker + PG + Redis + SearXNG + Caddy
│   ├── Caddyfile                      # TLS reverse proxy configuration
│   └── searxng/                       # SearXNG configuration volume
│
├── scripts/
│   └── migrate.py                     # Alembic migration runner (called on container start)
│
├── examples/
│   ├── deep-research-platform.html    # Rich example UI with glassmorphism + PDF export
│   └── third-party-client.html        # Example SaaS client integration
│
├── cli.py                             # Zero-dependency developer CLI (stdlib only)
├── alembic.ini                        # Alembic configuration
├── pyproject.toml                     # Project metadata + dependencies
├── requirements.txt                   # Pinned production dependencies
└── .env.example                       # Environment variable template
```

---

## Technology Stack

### Backend

| Technology | Version | Role | Rationale |
|---|---|---|---|
| **Python** | 3.12+ | Runtime | Mature async ecosystem; `asyncio.gather` for concurrent fetches |
| **FastAPI** | 0.111 | HTTP framework | Auto-generated OpenAPI docs; native async/await; Starlette middleware |
| **Uvicorn** | 0.29 | ASGI server | Production-grade async server with Gunicorn workers option |
| **Pydantic** | 2.7 | Data validation | Settings management + request/response schemas |
| **SQLAlchemy** | 2.0 | ORM | Async-native ORM with `asyncpg` dialect |
| **ARQ** | 0.25 | Job queue | Redis-backed async task queue; native Python async; exponential backoff |
| **httpx** | 0.27 | HTTP client | Async HTTP for URL fetching with timeout and connection pooling |
| **Playwright** | 1.60+ | Browser automation | Headless Chromium for JS-rendered pages |
| **BeautifulSoup4** | 4.12 | HTML parsing | Fast HTML-to-text stripping |
| **Cryptography** | 42.0 | Fernet encryption | Symmetric encryption for API keys and webhook secrets at rest |
| **prometheus-fastapi-instrumentator** | 7.1 | Metrics | Automatic Prometheus metric exposure on `/metrics` |
| **WeasyPrint** | latest | PDF generation | HTML→PDF rendering for report export |
| **markdown2** | latest | Markdown processing | Report HTML conversion for PDF pipeline |

### Frontend

| Technology | Role |
|---|---|
| **Vite + React + TypeScript** | Product landing page / debugging console |
| **Tailwind CSS** | Utility-first styling |
| **Lucide React** | Icon set |

### Database & Storage

| Technology | Role | Key Feature Used |
|---|---|---|
| **PostgreSQL 16** | Primary data store | Async driver via asyncpg |
| **pgvector** | Vector similarity search | `Vector(1536)` column; `<=>` cosine distance operator |
| **Alembic** | Database migrations | Async `env.py` for schema evolution |
| **Redis 7** | Job queue + webhook retry | ARQ list-based queue; sorted set for deferred jobs |

### Infrastructure

| Technology | Role |
|---|---|
| **Docker** | Container runtime |
| **Docker Compose** | Local + production stack orchestration |
| **Caddy 2** | Automatic TLS reverse proxy |
| **SearXNG** | Self-hosted search meta-engine (no external API key required) |
| **Ollama** | Local LLM server for air-gap deployments |

### CI/CD

| Tool | Role |
|---|---|
| **GitHub Actions** | CI pipeline (push + PR on `main`) |
| **astral-sh/uv** | Fast Python dependency management |
| **Ruff** | Linting + formatting |
| **pytest + pytest-asyncio** | Test runner |

---

## API Documentation

All authenticated endpoints require:

```
Authorization: Bearer <your-llm-api-key>
```

The provider is auto-detected from the key prefix. Override with headers:

```
X-Provider: openai_compatible
X-Base-Url: http://localhost:11434/v1
X-Model: llama3.1:70b
```

### Endpoints

#### Research

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/v1/research` | Submit a new research job | Required |
| `GET` | `/v1/research/{job_id}` | Poll job status + partial/full results | Required |
| `GET` | `/v1/research/{job_id}/stream` | Stream live progress via SSE | Required |
| `DELETE` | `/v1/research/{job_id}` | Cancel a running job | Required |
| `POST` | `/v1/research/{job_id}/chat` | Chat with a completed report | Required |

#### Reports

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/v1/reports/{report_id}/export?format=md` | Export as Markdown | Required |
| `GET` | `/v1/reports/{report_id}/export?format=json` | Export as JSON with citations | Required |
| `GET` | `/v1/reports/{report_id}/export?format=pdf` | Export as PDF | Required |

#### Knowledge Graph

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/v1/knowledge-graph/search?q=...&limit=10` | Semantic search across all past claims | Required |

#### Webhooks

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/v1/webhooks` | Register a webhook endpoint | Required |
| `GET` | `/v1/webhooks` | List all registered endpoints | Required |
| `DELETE` | `/v1/webhooks/{webhook_id}` | Deregister a webhook endpoint | Required |

#### System

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/health` | Basic health check | Public |
| `GET` | `/metrics` | Prometheus metrics | Public |
| `GET` | `/docs` | OpenAPI Swagger UI | Public |

---

### Request & Response Examples

#### `POST /v1/research`

**Request:**
```json
{
  "query": "What are the competitive dynamics in the solid-state battery market as of 2026?",
  "max_rounds": 3,
  "priority": 2,
  "provider": "anthropic",
  "api_key": "sk-ant-...",
  "model": "claude-3-5-sonnet-latest",
  "metadata": {
    "requester": "analyst-team-a",
    "project_id": "proj_battery_2026"
  }
}
```

**Response `202 Accepted`:**
```json
{
  "id": "job_a1b2c3d4e5f6",
  "status": "queued",
  "query": "What are the competitive dynamics...",
  "created_at": "2026-06-19T01:38:00.000000+00:00"
}
```

#### `GET /v1/research/{job_id}` (completed)

```json
{
  "id": "job_a1b2c3d4e5f6",
  "status": "completed",
  "query": "What are the competitive dynamics...",
  "created_at": "2026-06-19T01:38:00Z",
  "started_at": "2026-06-19T01:38:02Z",
  "finished_at": "2026-06-19T01:42:14Z",
  "error": null,
  "rounds_completed": 3,
  "partial_sources": [
    {
      "url": "https://example.com/solid-state-batteries",
      "title": "QuantumScape Q1 2026 Update",
      "excerpt": "QuantumScape reported a 400 Wh/kg energy density...",
      "round_number": 1
    }
  ],
  "report": {
    "id": "rpt_f1e2d3c4b5a6",
    "summary": "The solid-state battery market is led by four players...",
    "body_md": "# Solid-State Battery Competitive Landscape\n\n## Executive Summary\n...",
    "citations": [
      {"id": "src_1", "url": "https://example.com/...", "title": "QuantumScape Q1 2026"}
    ]
  }
}
```

#### SSE Event Stream (`GET /v1/research/{job_id}/stream`)

```
event: progress
data: {"status": "running", "progress_pct": 33, "source_count": 7, "error": null}

event: progress
data: {"status": "running", "progress_pct": 66, "source_count": 14, "error": null}

event: progress
data: {"status": "completed", "progress_pct": 100, "source_count": 21, "error": null}
```

#### Webhook Payload

```json
{
  "event": "research.completed",
  "job_id": "job_a1b2c3d4e5f6",
  "status": "completed",
  "query": "What are the competitive dynamics...",
  "created_at": "2026-06-19T01:38:00Z",
  "finished_at": "2026-06-19T01:42:14Z",
  "report_url": "/v1/reports/rpt_f1e2d3c4b5a6"
}
```

Headers:
```
X-Webhook-Signature: t=1718758934,v1=abc123def456...
X-Webhook-Timestamp: 1718758934
```

---

### Error Codes

| HTTP Status | Code | Description |
|---|---|---|
| `400` | `BAD_REQUEST` | Invalid request body; unsupported export format |
| `401` | `UNAUTHORIZED` | Missing `Authorization` header; unrecognized key prefix |
| `404` | `NOT_FOUND` | Job or report does not exist |
| `409` | `CONFLICT` | Cannot cancel a job that is already `completed`, `failed`, or `cancelled` |
| `500` | `INTERNAL_ERROR` | Unexpected server error; PDF dependencies missing |

---

## Database Design

```mermaid
erDiagram
    research_jobs {
        string id PK "job_<12hex>"
        text query
        string status "queued|running|completed|failed|cancelled"
        int priority "1 (high) to 5 (low)"
        int max_rounds "1-5, default 3"
        int progress_pct "0-100"
        string category "nullable"
        string model_override "nullable"
        text error "nullable"
        text metadata_json "JSONB: transient_backend (encrypted)"
        datetime created_at
        datetime started_at "nullable"
        datetime finished_at "nullable"
    }

    reports {
        string id PK "rpt_<12hex>"
        string job_id FK
        text summary
        text content_md
        text content_json "JSONB: {citations: [...]}"
        datetime created_at
    }

    sources {
        string id PK "src_<12hex>"
        string job_id FK
        text url
        text title "nullable"
        text excerpt "nullable"
        int round_number
        int trust_score "0-100, nullable"
        text flags "nullable"
        datetime fetched_at
    }

    claims {
        string id PK "clm_<12hex>"
        string job_id FK
        string source_id FK
        text fact
        vector embedding "Vector(1536) pgvector"
        int trust_score "nullable"
        string contradicts_claim_id FK "self-ref, nullable"
        datetime created_at
    }

    usage_records {
        string id PK "usg_<12hex>"
        string job_id FK
        int tokens_in
        int tokens_out
        int sources_fetched
        int search_queries_issued
        int duration_seconds
        datetime created_at
    }

    webhook_endpoints {
        string id PK "wh_<12hex>"
        text url
        bytes secret "Fernet-encrypted"
        bool is_active
    }

    audit_log {
        int id PK "auto-increment"
        string method
        string path
        text query_text "nullable (POST /v1/research only)"
        int response_status
        int duration_ms
        string ip_address
        string user_agent
        datetime timestamp
    }

    research_jobs ||--o{ sources : "job_id"
    research_jobs ||--o{ claims : "job_id"
    research_jobs ||--o| reports : "job_id"
    research_jobs ||--o| usage_records : "job_id"
    sources ||--o{ claims : "source_id"
    claims ||--o| claims : "contradicts_claim_id"
```

### Data Retention Policy

| Table | Retention | Notes |
|---|---|---|
| `research_jobs` | Indefinite | Soft-delete via `status='cancelled'` |
| `reports` | Indefinite | Regenerated on-demand if missing |
| `sources` | Per-job lifetime | Cascade deleted on job delete |
| `claims` | Per-job lifetime | Cascade deleted on job delete; embeddings are expensive |
| `usage_records` | Indefinite | Billing source of truth |
| `audit_log` | 30 days (configurable) | Cleaned by ARQ cron `cleanup_audit_log` |
| `webhook_endpoints` | Until revoked | `is_active=False` soft-disables |

---

## Configuration

All configuration is driven by environment variables, managed through Pydantic `BaseSettings`.

### Core Settings

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | `postgresql+asyncpg://user:pass@host/dbname` |
| `REDIS_URL` | ✅ | — | `redis://:password@host:6379/0` |
| `SECRET_KEY` | ✅ | — | Fernet key for encrypting API keys/webhook secrets at rest. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ENVIRONMENT` | ❌ | `development` | `development` or `production` |
| `MAX_RESEARCH_ROUNDS` | ❌ | `3` | Global max rounds cap (individual jobs can set lower) |
| `EXTRACTION_CONCURRENCY` | ❌ | `3` | Max concurrent URL fetch+extract operations per job |
| `SEARXNG_URL` | ❌ | `http://searxng:8080` | SearXNG REST endpoint |
| `WEBHOOK_MAX_RETRIES` | ❌ | `5` | Max webhook delivery attempts before marking failed |
| `AUDIT_RETENTION_DAYS` | ❌ | `365` | Days to retain audit log entries |
| `EXPORT_CACHE_TTL_SECONDS` | ❌ | `86400` | TTL for cached export files (24h) |

### Docker Compose Variables (deploy/.env)

| Variable | Default | Description |
|---|---|---|
| `PG_PASSWORD` | `devpassword` | PostgreSQL password |
| `REDIS_PASSWORD` | `devredispass` | Redis `requirepass` value |
| `SECRET_KEY` | `changeme-dev-secret-32chars-min` | **Must be changed in production** |

> [!CAUTION]
> Never use the default `SECRET_KEY` in production. All webhook secrets and LLM API keys stored in the database are encrypted with this key. Rotation requires re-encrypting all stored secrets.

---

## Installation

### Prerequisites

| Dependency | Minimum Version | Purpose |
|---|---|---|
| Docker | 24.0+ | Container runtime |
| Docker Compose | 2.20+ (plugin) | Stack orchestration |
| Python | 3.12+ | Local development only |
| uv | 0.4+ | Fast Python package manager (local dev) |

---

### Docker Setup (Recommended)

This is the standard path for both local development and production.

```bash
# 1. Clone the repository
git clone https://github.com/avirooppal/Vanta-Deep-Research-API
cd Vanta-Deep-Research-API

# 2. Configure environment
cp deploy/.env.example deploy/.env
# Edit deploy/.env — set SECRET_KEY to a unique random string

# 3. Build and start all services
#    Services: api, worker, postgres (pgvector), redis, searxng, caddy
cd deploy
docker compose up -d --build

# 4. Tail logs to confirm startup
docker compose logs -f api worker
```

The API will be available at `http://localhost:8000`. The built-in debug console is at `http://localhost:8000/`.

---

### Local Development Setup

```bash
# 1. Clone
git clone https://github.com/avirooppal/Vanta-Deep-Research-API
cd Vanta-Deep-Research-API

# 2. Install uv (if not installed)
pip install uv

# 3. Install dependencies
uv pip install -r requirements.txt

# 4. Install Playwright Chromium browser
playwright install chromium
playwright install-deps

# 5. Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, REDIS_URL, SECRET_KEY

# 6. Run database migrations
uv run python scripts/migrate.py

# 7. Start services (requires running PostgreSQL + Redis + SearXNG locally)

# Terminal 1: API Server
uv run uvicorn api.app:app --reload --port 8000

# Terminal 2: ARQ Worker
uv run arq core.queue.worker.WorkerSettings
```

> [!TIP]
> You can run only PostgreSQL, Redis, and SearXNG via Docker while running the Python processes locally for faster iteration:
> ```bash
> docker compose up -d postgres redis searxng
> ```

---

### Air-Gap / Fully Offline Setup

For environments where **zero bytes leave the network**:

1. Pull and save all Docker images offline:
   ```bash
   docker pull pgvector/pgvector:pg16
   docker pull redis:7-alpine
   docker pull searxng/searxng:latest
   docker pull ollama/ollama:latest
   docker save -o vanta-stack.tar pgvector/pgvector:pg16 redis:7-alpine searxng/searxng:latest
   # Transfer to air-gapped host
   docker load -i vanta-stack.tar
   ```

2. Start Ollama and pull your model:
   ```bash
   docker run -d --gpus all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
   docker exec ollama ollama pull llama3.1:70b
   ```

3. Submit research jobs with explicit local LLM configuration:
   ```bash
   curl -X POST http://localhost:8000/v1/research \
     -H "Authorization: Bearer dummy-local-key" \
     -H "X-Provider: openai_compatible" \
     -H "X-Base-Url: http://ollama:11434/v1" \
     -H "X-Model: llama3.1:70b" \
     -H "Content-Type: application/json" \
     -d '{"query": "Latest EU AI regulation updates", "max_rounds": 2}'
   ```

---

### Verification

```bash
# Health check
curl http://localhost:8000/health

# Submit a test job (replace with your actual key)
curl -X POST http://localhost:8000/v1/research \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{"query": "What is pgvector?", "max_rounds": 1}'

# Expected: 202 Accepted with {id, status: "queued", ...}

# Poll job status
curl http://localhost:8000/v1/research/<job_id> \
  -H "Authorization: Bearer sk-..."

# Check Prometheus metrics
curl http://localhost:8000/metrics
```

---

## Developer CLI

`cli.py` is a zero-dependency CLI (Python stdlib only) for submitting jobs and tracking progress.

```bash
# Submit a job and wait for completion, pretty-print report to stdout
uv run python cli.py submit "What are the latest advancements in quantum error correction?" \
  --api-key "sk-..." \
  --max-rounds 2 \
  --api-url "http://localhost:8000"

# Save the report to a Markdown file
uv run python cli.py submit "Solid-state battery competitive landscape 2026" \
  --api-key "sk-ant-..." \
  --max-rounds 3 \
  --output "battery_report.md"

# Use a local Ollama model
uv run python cli.py submit "EU AI Act summary" \
  --api-key "dummy" \
  --provider "openai_compatible" \
  --base-url "http://localhost:11434/v1" \
  --model "llama3.1:8b"
```

**CLI flags:**

| Flag | Default | Description |
|---|---|---|
| `query` | (required) | The research question |
| `--api-key` | (required) | LLM API key passed as `Authorization: Bearer` |
| `--max-rounds` | `3` | Number of research iterations |
| `--api-url` | `http://localhost:8000` | Vanta API base URL |
| `--output` | None | Path to save Markdown report |
| `--provider` | Auto-detected | Override LLM provider |
| `--base-url` | Auto-detected | Override LLM base URL |
| `--model` | Auto-detected | Override LLM model name |

---

## Development Workflow

### Branching Strategy

```
main          ← stable, CI-protected
feature/*     ← feature development
fix/*         ← bug fixes
chore/*       ← tooling, deps, docs
```

### Commit Conventions

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add citation verifier agent
fix: handle empty findings list in synthesizer
chore: pin httpx to 0.27.0
docs: update API reference for /v1/knowledge-graph/search
refactor: extract trust scoring into ValidatorAgent
test: add integration test for webhook delivery retry
```

### Pull Request Process

1. Open a PR against `main` with a clear description and linked issue.
2. CI must pass: Ruff lint + all pytest tests green.
3. At least one review approval required.
4. Squash-merge is preferred for feature branches.

### Code Standards

- **Formatting/linting:** `ruff check .` and `ruff format .`
- **Type hints:** All public functions and methods must have type annotations.
- **Async:** All I/O must be `async`; no blocking calls in the hot path.
- **Tests:** New routes and agents require at minimum a unit test.

---

## Testing Strategy

```mermaid
flowchart LR
    UT["Unit Tests\ntests/unit/\nMocked DB + LLM\nFast: < 1s per test"]
    IT["Integration Tests\ntests/integration/\nFastAPI TestClient\nMocked DB sessions\nReal middleware chain"]
    E2E["E2E Tests\ntests/e2e/\nRequires live stack\n(DB, Redis, SearXNG)"]

    UT --> IT --> E2E
```

### Running Tests

```bash
# Run all tests (unit + integration)
uv run pytest

# Run with verbose output
uv run pytest -v

# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/

# Run with test env vars (sqlite in-memory for speed)
DATABASE_URL=sqlite+aiosqlite:///:memory: \
REDIS_URL=redis://localhost:6379/0 \
SECRET_KEY=test_secret_key_32_chars_minimum \
uv run pytest

# Run linter
uv run ruff check .
```

### Test Coverage Expectations

| Layer | Target Coverage | Strategy |
|---|---|---|
| Route handlers | 80%+ | Integration tests with mocked DB sessions |
| Agent logic | 70%+ | Unit tests with deterministic LLM stubs |
| Worker tasks | 60%+ | Unit tests mocking `run_research` and DB |
| Middleware | 90%+ | Integration tests exercising full middleware chain |

### Mocking Conventions

Tests mock at the boundary layer:
- **`get_db_session`** → replaced with an `AsyncMock` returning pre-configured model instances.
- **`create_pool`** (Redis) → `AsyncMock` to avoid real Redis in unit/integration tests.
- **LLM calls** → deterministic stub returning fixed `LLMResponse` objects.

---

## Security Architecture

### Authentication Model

Vanta uses **Bring Your Own Key (BYOK)**: the LLM API key passed in `Authorization: Bearer` is the authenticating credential. It is:

1. **Never stored in plaintext** — encrypted with Fernet before being written to `metadata_json` in the `research_jobs` table.
2. **Decrypted only at task execution time** by the ARQ worker, in memory, and used directly to initialize `LLMClient`.
3. **Never logged** — the `auth_middleware` populates `request.state.transient_backend` but the audit log middleware does not capture the key value.

```mermaid
flowchart LR
    Client -- "Bearer sk-..." --> Auth["auth_middleware\nDetect provider\nDo NOT store key in log"]
    Auth -- "transient_backend dict" --> Route["POST /v1/research"]
    Route -- "Fernet.encrypt(api_key)" --> DB[("PostgreSQL\nmetadata_json JSONB")]
    DB -- "encrypted bytes" --> Worker["ARQ Worker\nFernet.decrypt(enc_key)\nBuild LLMClient"]
    Worker -- "api_key in memory only" --> LLM["LLM Provider"]
```

### Provider Auto-Detection Logic

| Key Prefix | Detected Provider | Default Model |
|---|---|---|
| `sk-ant-` | `anthropic` | `claude-3-5-sonnet-latest` |
| `sk-or-` | `openrouter` | `openrouter/free` |
| `sk-` | `openai` | `gpt-4o` |
| `AIza` | `openai_compatible` (Gemini) | `gemini-2.5-flash` |
| *(any)* + `X-Provider` header | Custom | Per `X-Model` header |

### Secrets at Rest

All secrets are encrypted with [Fernet symmetric encryption](https://cryptography.io/en/latest/fernet/) (AES-128-CBC + HMAC-SHA256):

- **LLM API keys** — encrypted in `research_jobs.metadata_json`
- **Webhook secrets** — encrypted in `webhook_endpoints.secret`

The `SECRET_KEY` environment variable is the Fernet key. It must be a valid Fernet key (32-byte URL-safe base64). Generate with:

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### Audit Log

`api/middleware/audit_log.py` writes an `AuditLog` row for every request:

```
method | path | query_text (POST /v1/research only) | response_status | duration_ms | ip_address | user_agent | timestamp
```

The `AuditLog` table is **append-only** — no application code issues `UPDATE` or `DELETE` against it. A cron ARQ task (`cleanup_audit_log`) deletes rows older than `AUDIT_RETENTION_DAYS` (configurable, default 365).

### Security Controls Summary

| Control | Implementation |
|---|---|
| Transport security | Caddy 2 automatic TLS (Let's Encrypt) |
| Secrets at rest | Fernet AES-128 encryption |
| Key rotation support | Re-encrypt on `SECRET_KEY` rotation |
| Prompt injection mitigation | Fetched page content is wrapped in semantic fences before LLM extraction |
| Replay attack prevention | Webhook `X-Webhook-Timestamp` + `|now - t| < 300s` validation |
| CORS | Configurable via FastAPI `CORSMiddleware` |
| Request tracing | `X-Request-ID` propagated through middleware chain |

---

## Observability

### Logging

`core/logging.py` sets up structured logging with a `request_id_var` context variable. Every log line emitted during a request carries the `X-Request-ID` value, enabling full request tracing in log aggregators.

```python
# Example log output
INFO  request_id=a1b2c3d4 run_research_job job_id=job_xyz status=running
INFO  request_id=a1b2c3d4 ValidatorAgent trust_score=82 url=https://example.com
```

### Metrics

`prometheus-fastapi-instrumentator` automatically instruments all FastAPI routes and exposes metrics at `GET /metrics`:

| Metric | Description |
|---|---|
| `http_requests_total` | Request count by method, path, status |
| `http_request_duration_seconds` | Request latency histogram |
| `http_requests_in_progress` | Concurrent in-flight requests |

Scrape with Prometheus and visualize in Grafana using the [FastAPI dashboard](https://grafana.com/grafana/dashboards/17461).

### Health Endpoints

| Endpoint | Returns | Use |
|---|---|---|
| `GET /health` | `{"status": "ok"}` | Basic liveness |
| `GET /health/ready` | `{"status": "ok"}` | Readiness (DB connectivity check) |
| `GET /health/live` | `{"status": "ok"}` | Kubernetes liveness probe |

### Distributed Tracing (Planned)

OpenTelemetry integration is on the roadmap. The `X-Request-ID` header provides manual trace correlation in the interim.

---

## Deployment Architecture

### Local / Development

```mermaid
flowchart TD
    Browser["Browser / curl / CLI"] --> Caddy["Caddy :80"]
    Caddy --> API["FastAPI :8000"]
    API --> PG[("PostgreSQL :5433\n(pgvector/pgvector:pg16)")]
    API --> Redis[("Redis :6379")]
    Redis --> Worker["ARQ Worker"]
    Worker --> PG
    Worker --> SearXNG["SearXNG :8085"]
```

### Production (Kubernetes — Planned)

```mermaid
flowchart TD
    Internet --> Ingress["Kubernetes Ingress\n(NGINX / Traefik)"]
    Ingress --> APIDeployment["api Deployment\n(3+ replicas, HPA)"]
    APIDeployment --> PGStateful[("postgres StatefulSet\n(+ read replicas)")]
    APIDeployment --> RedisStateful[("redis StatefulSet\n(Sentinel mode)")]
    RedisStateful --> WorkerDeployment["worker Deployment\n(auto-scale on queue depth)"]
    WorkerDeployment --> PGStateful
    WorkerDeployment --> SearXNGDeploy["searxng Deployment"]
```

### Scaling Strategy

| Component | Scaling Approach | Bottleneck |
|---|---|---|
| API servers | Horizontal (stateless) | Memory per connection |
| ARQ workers | Horizontal (add replicas) | LLM API rate limits |
| PostgreSQL | Vertical + read replicas | Write throughput for claims table |
| Redis | Sentinel for HA; Cluster for scale | Queue depth during bursts |
| SearXNG | Horizontal (independent instances) | External search engine rate limits |

---

## CI/CD Pipeline

```mermaid
flowchart LR
    Push["Git push to main\nor Pull Request"] --> Checkout["actions/checkout@v4"]
    Checkout --> UV["astral-sh/setup-uv@v3\nInstall uv"]
    UV --> Python["actions/setup-python@v5\nPython 3.12"]
    Python --> Install["uv sync\nInstall all dependencies"]
    Install --> Lint["uv run ruff check .\nLint + style check"]
    Lint --> Test["uv run pytest\nDATABASE_URL=sqlite+aiosqlite:///:memory:\nSECRET_KEY=test_secret_key"]
    Test --> Done["✅ CI Passed"]
    Lint -- "lint error" --> Fail["❌ CI Failed"]
    Test -- "test failure" --> Fail
```

**CI Jobs** (`.github/workflows/ci.yml`):

1. **Checkout** — fetch source at the commit SHA.
2. **Install uv** — Astral's official setup action.
3. **Set up Python 3.12** — via `actions/setup-python`.
4. **Install dependencies** — `uv sync` (reads `pyproject.toml` and `uv.lock`).
5. **Ruff lint** — `uv run ruff check .` — fails on any lint error.
6. **Pytest** — in-memory SQLite + test `SECRET_KEY`; no external services required.

---

## Performance Considerations

### LLM Call Budget Per Job

A single research job with `max_rounds=3` makes approximately:

| LLM Call | Agent | Frequency | Approximate Tokens |
|---|---|---|---|
| Coordinator decision | CoordinatorAgent | 1× per round | ~500 in, ~10 out |
| Sub-query generation | SearchAgent | 1× per round | ~800 in, ~200 out |
| Source validation | ValidatorAgent | 1× per URL (up to 15) | ~1500 in, ~50 out |
| Fact extraction | ExtractorAgent | 1× per URL (up to 15) | ~3000 in, ~500 out |
| Contradiction detection | ContradictionAgent | 1× per round | ~5000 in, ~300 out |
| Final synthesis | SynthesizerAgent | 1× | ~20000 in, ~3000 out |
| Citation verification | CitationVerifierAgent | 1× | ~5000 in, ~500 out |

**Total per 3-round job:** ~120,000–180,000 tokens in; ~15,000–25,000 tokens out (varies significantly by model and findings volume).

### Fetch Concurrency

URL fetching is bounded by `asyncio.Semaphore(settings.extraction_concurrency)` (default `3`). Increasing this value speeds up the fetching phase at the cost of higher memory usage and potential rate-limiting from target servers.

### Context Window Management

`SynthesizerAgent` implements a character-budget cap (`MAX_SYNTHESIS_CHARS = 80000`) to avoid exceeding LLM context windows. It prioritizes findings from the most recent rounds and truncates earlier rounds with a note.

### Caching

- **Report exports** are not currently cached at the HTTP layer; each PDF request re-runs WeasyPrint.
- **pgvector queries** benefit from PostgreSQL's IVFFlat index (to be added — see Roadmap).

---

## Failure Handling

```mermaid
flowchart TD
    Job["Research job running"] --> Err{"Exception?"}
    Err -- "No" --> Done["Completed ✓"]
    Err -- "Yes: LLM timeout / rate limit" --> ARQ["ARQ retry (up to 3x)\nJob stays 'running'"]
    Err -- "Yes: Unrecoverable" --> Failed["job.status = 'failed'\njob.error = str(exc)\nWebhook: research.failed"]

    Webhook["Webhook delivery"] --> WHErr{"HTTP error?"}
    WHErr -- "No" --> WHDone["Delivered ✓"]
    WHErr -- "Yes (attempt < 5)" --> WHRetry["Re-enqueue with backoff\n10s → 30s → 2m → 10m → 1h"]
    WHRetry --> Webhook
    WHErr -- "Yes (attempt = 5)" --> WHFail["LOG permanent failure\nEndpoint not auto-disabled"]

    Cancel["DELETE /v1/research/{id}"] --> SetStatus["job.status = 'cancelled'\njob.finished_at = now()"]
    SetStatus --> Engine["cancel_event.set()\nEngine checks at top of each round\nLoop exits cleanly"]
```

### Retry Behavior

| Failure Type | Retry | Mechanism |
|---|---|---|
| ARQ task failure | Yes (3×) | ARQ built-in retry with job-level backoff |
| Webhook HTTP 5xx | Yes (5×) | Manual re-enqueue via `_defer_by` |
| Webhook HTTP 4xx | No | Client error — no retry (misconfigured endpoint) |
| LLM API rate limit | Yes (within task) | httpx retry on 429 (provider-specific) |
| URL fetch failure | Skip URL | `fetch_url` returns `page.success=False`; URL silently skipped |

---

## Troubleshooting Guide

| Issue | Likely Cause | Resolution |
|---|---|---|
| `401 Missing or invalid Authorization header` | No `Authorization` header sent | Add `Authorization: Bearer <your-llm-key>` |
| `401 Could not detect LLM provider` | Non-standard key prefix | Add `X-Provider: openai_compatible` header |
| Job stuck in `queued` indefinitely | ARQ worker not running | Run `docker compose ps` — ensure `worker` container is up; check `docker compose logs worker` |
| Job fails with `No LLM backend configured` | API key not passed correctly or Fernet decrypt failed | Verify `SECRET_KEY` in `.env` matches the one used when the job was submitted |
| `500 PDF generation dependencies not installed` | `weasyprint` or `markdown2` not installed | Run `pip install weasyprint markdown2` or rebuild the Docker image |
| `pgvector extension not found` | Wrong PostgreSQL image (plain `postgres:16` instead of `pgvector/pgvector:pg16`) | Check `docker-compose.yml` uses `pgvector/pgvector:pg16` image |
| No sources found (empty report) | SearXNG not reachable | Check `SEARXNG_URL` in `.env`; verify `docker compose ps searxng` |
| SSE stream immediately closes | Job already completed or client timeout | Connect to SSE before submitting, or poll `GET /v1/research/{id}` instead |
| Webhook never arrives | Endpoint URL unreachable from container network | Ensure the webhook URL is accessible from within the Docker network; use `host.docker.internal` for local receivers |
| Alembic migration fails | Database URL mismatch or pg_isready not satisfied | Confirm `DATABASE_URL` is correct; check `docker compose logs postgres` |
| High memory usage | Large page content held during extraction | Lower `EXTRACTION_CONCURRENCY` or reduce `max_rounds` |

---

## FAQ

**Q: Do I need a paid LLM API key?**

A: Not necessarily. OpenRouter has a free tier (`sk-or-...`). For fully local operation, point to Ollama with `X-Provider: openai_compatible` and a local model. Note that quality of research output is significantly affected by model capability.

**Q: Is my research query data sent to any third party?**

A: Only to the LLM provider and search engine you configure. Vanta itself does not have a telemetry backend. If you use SearXNG for search and Ollama for LLM, no data leaves your network.

**Q: Can I run multiple workers for higher throughput?**

A: Yes. Workers are stateless; scale the `worker` service in `docker-compose.yml`:
```yaml
worker:
  deploy:
    replicas: 4
```

**Q: How do I search across all past research sessions?**

A: Use `GET /v1/knowledge-graph/search?q=your+topic&limit=10`. This performs a vector similarity search across all `claims` rows using pgvector.

**Q: Can I use a custom search engine instead of SearXNG?**

A: Yes, via the plugin system. Implement `BaseSearchPlugin` in `core/plugins/registry.py` and register it. Brave Search and Tavily are planned as built-in providers in a future release.

**Q: What happens if I cancel a job mid-research?**

A: The `DELETE /v1/research/{id}` endpoint sets `job.status='cancelled'`. The ARQ worker's `on_progress` callback checks for this status at the end of each round and sets the `cancel_event`. The engine loop exits cleanly at the top of the next round. Partial sources written so far remain in the database.

**Q: How do I rotate the `SECRET_KEY`?**

A: Currently, all Fernet-encrypted values (API keys in job metadata, webhook secrets) would need to be re-encrypted. A key rotation utility is on the roadmap. For now, plan key rotation carefully and avoid rotating during active job processing.

**Q: Are there rate limits?**

A: Vanta itself has no built-in rate limiting in v0.2. The architecture document describes a Redis sliding-window rate limiter planned for a future release. In the interim, LLM provider rate limits naturally throttle throughput.

---

## Roadmap

### Near-Term (v0.3)

- [ ] **Brave Search + Tavily** as built-in search provider options (no SearXNG required)
- [ ] **Redis sliding-window rate limiter** for per-client job submission throttling
- [ ] **pgvector IVFFlat index** on `claims.embedding` for sub-millisecond similarity search at scale
- [ ] **DOCX export** via `python-docx` with sources table and metadata footer
- [ ] **Admin dashboard** (Starlette HTML) for job monitoring, audit log viewing, usage export

### Medium-Term (v0.4–0.5)

- [ ] **Multi-tenancy** — Organisation + API key scoping with PostgreSQL Row-Level Security
- [ ] **OpenTelemetry integration** — distributed tracing with Jaeger/Tempo
- [ ] **Kubernetes Helm chart** — production-grade k8s deployment for enterprise customers
- [ ] **Per-org LLM backend registry** — register and test multiple LLM endpoints per tenant
- [ ] **Streaming synthesis** — stream Synthesizer output tokens directly to SSE clients

### Long-Term

- [ ] **Plugin SDK** — stable API for community-contributed search and extraction plugins
- [ ] **Async report generation** — progressive report writing (sections complete before full synthesis)
- [ ] **Air-gap Helm variant** — Ollama sidecar + SearXNG bundled in a single Helm chart
- [ ] **SOC 2 readiness** — immutable audit log export, key rotation utility, compliance reporting
- [ ] **MCP server** — expose research capabilities as an MCP tool for agent frameworks

---

## Contributing

Contributions are welcome. Please follow these steps:

1. **Fork** the repository and create a feature branch from `main`.
2. **Run the test suite** locally before opening a PR:
   ```bash
   DATABASE_URL=sqlite+aiosqlite:///:memory: REDIS_URL=redis://localhost:6379/0 SECRET_KEY=test_secret_key_32chars uv run pytest
   uv run ruff check .
   ```
3. **Write tests** for new functionality. PRs without tests for new routes or agents will request changes.
4. **Update documentation** if you're changing the API surface, configuration, or architecture.
5. **Open a pull request** against `main` with a clear description.

**Local development with Docker for services:**

```bash
# Start only infrastructure services
docker compose up -d postgres redis searxng

# Run API and worker locally with hot-reload
uv run uvicorn api.app:app --reload --port 8000 &
uv run arq core.queue.worker.WorkerSettings &
```

---

## License

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2026 avirooppal

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

---

## Appendix

### Glossary

| Term | Definition |
|---|---|
| **BYOK** | Bring Your Own Key — the LLM API key passed as a Bearer token is used directly, with no key stored server-side in plain text |
| **IterResearch** | The multi-round iterative research loop algorithm ported from the Odysseus project |
| **ARQ** | Async Redis Queue — the Python async job queue library used for background task execution |
| **pgvector** | PostgreSQL extension that adds vector similarity search capabilities |
| **Finding** | A structured fact extracted from a fetched web page, consisting of `url`, `title`, `facts`, `round_number`, and `trust_score` |
| **Claim** | A single atomic fact from a `Finding`, embedded as a 1536-dimensional vector and stored in the `claims` table for knowledge graph queries |
| **ValidatedSource** | A fetched page that has passed `ValidatorAgent` scoring with `trust_score ≥ 30` |
| **Transient backend** | An ephemeral LLM configuration derived from request headers and stored encrypted in the job metadata; no persistent LLM config table is used in BYOK mode |
| **ReportOutput** | The final data structure returned by the research engine: `query`, `summary`, `body_md`, `citations` |
| **SearXNG** | A self-hosted, privacy-respecting metasearch engine that aggregates results from Google, Bing, DuckDuckGo, and others |

### LLM Provider Support Matrix

| Provider | Key Prefix | `X-Provider` Value | Embedding Support | Notes |
|---|---|---|---|---|
| OpenAI | `sk-` | `openai` | ✅ `text-embedding-3-small` | Default model: `gpt-4o` |
| Anthropic | `sk-ant-` | `anthropic` | ❌ (uses OpenAI for embeddings) | Default model: `claude-3-5-sonnet-latest` |
| Google Gemini | `AIza` | `openai_compatible` | ❌ | Via OpenAI-compatible Gemini endpoint |
| OpenRouter | `sk-or-` | `openrouter` | ❌ | Default: `openrouter/free` |
| Azure OpenAI | *(any)* | `azure_openai` | ✅ | Set `X-Base-Url` to Azure endpoint |
| Ollama (local) | *(any)* | `openai_compatible` | ✅ (if model supports) | Set `X-Base-Url` to `http://ollama:11434/v1` |
| vLLM / Groq / Together | *(any)* | `openai_compatible` | ✅ (model-dependent) | Set `X-Base-Url` to provider endpoint |

### State & Storage Map

| Data | Where | Format | Retention |
|---|---|---|---|
| Research jobs | PostgreSQL `research_jobs` | Row | Indefinite |
| Report content | PostgreSQL `reports` | Text (md) + JSONB | Indefinite |
| Source excerpts | PostgreSQL `sources` | Text + URL | Cascade on job delete |
| Knowledge graph | PostgreSQL `claims` | Text + Vector(1536) | Cascade on job delete |
| Usage records | PostgreSQL `usage_records` | Row | Indefinite |
| Webhook config | PostgreSQL `webhook_endpoints` | Row (Fernet secret) | Until revoked |
| Audit log | PostgreSQL `audit_log` | Row (append-only) | `AUDIT_RETENTION_DAYS` (default 365) |
| Job queue | Redis list (ARQ) | Serialized args | Until consumed |
| Webhook retry | Redis sorted set | Payload + retry time | Until delivered or max attempts |

### References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [ARQ (Async Redis Queue)](https://arq-docs.helpmanual.io/)
- [pgvector](https://github.com/pgvector/pgvector)
- [SearXNG](https://docs.searxng.org/)
- [Fernet symmetric encryption](https://cryptography.io/en/latest/fernet/)
- [WeasyPrint PDF generation](https://doc.courtbouillon.org/weasyprint/stable/)
- [Playwright Python](https://playwright.dev/python/)
- [Caddy 2 documentation](https://caddyserver.com/docs/)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

<div align="center">

Built with ❤️ by [avirooppal](https://github.com/avirooppal) · [GitHub](https://github.com/avirooppal/Vanta-Deep-Research-API)

</div>
