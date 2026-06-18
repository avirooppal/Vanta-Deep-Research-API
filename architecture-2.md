# Vanta - What it is, How it's Used, & Execution Flow
> A comprehensive guide to Vanta: its purpose, use cases, and step-by-step operational walkthrough.

## What It Is
**Vanta** is a self-hosted, privacy-first Research-as-a-Service system. Built on the Odysseus `IterResearch` engine, it exposes a single-purpose REST API designed for enterprise deployment inside customer VPCs, air-gapped networks, and on-premise infrastructure. It takes a natural language query and autonomously runs a multi-round iterative research loop (plan → search → fetch → extract → synthesize) to produce a structured, highly-cited final report. 

It is designed entirely for system-to-system integration, featuring a headless API, robust webhook delivery, and tenant isolation, without any user-facing chat interfaces.

## How It Will Be Used
The API is meant to be integrated into existing enterprise workflows where deep, automated competitive intelligence or data gathering is required. 

**Common Integration Patterns:**
- **CI/CD & Automation Tools**: Integrating with Zapier, n8n, or internal cron jobs to run weekly competitor analysis or market reports.
- **Custom Internal Dashboards**: Embedded as a backend engine for internal analyst portals where users submit complex queries and receive formatted DOCX/PDF reports asynchronously.
- **Air-Gapped Environments**: Running completely offline using local LLMs (like Ollama) and local search (SearXNG) to process highly sensitive IP or health data (e.g., Pharma competitive intelligence) without any data ever leaving the customer's network.

Customers will typically submit a research job via the `POST /v1/research` endpoint and then either poll for results or rely on an asynchronous webhook delivery to receive the final cited report in Markdown, DOCX, or JSON format.

---

## The Lifecycle of a Request
While `architecture.md` provides a structural map of the codebase, the following sections detail exactly how the system processes a query from start to finish.

---

## 1. The Entrypoint: Job Submission

Everything begins when a client makes a `POST /v1/research` request to the FastAPI web server.

### What Happens:
1. **Authentication & Tenant Scoping**: The request passes through the `auth.py` middleware. The API key is verified via bcrypt against the `api_keys` table. The `org_id` is extracted and injected into the request state, isolating the request to a specific tenant.
2. **Job Record Creation**: Inside `api/routes/research.py`, a new `ResearchJob` row is created in the PostgreSQL database with a status of `queued`. The job includes the original `query`, `max_rounds`, and any `model_override` or `metadata`.
3. **Queueing**: The API server enqueues a background task named `run_research_job` in Redis using the `arq` library. The `job_id` is passed as the task payload.
4. **Response**: The API server responds immediately with a `202 Accepted`, returning the `job_id`. The client is now free to disconnect and poll the status endpoint or wait for a webhook.

---

## 2. The Worker: Picking Up the Job

The `arq` worker process runs concurrently and listens to the Redis queue.

### What Happens:
1. **Task Execution**: The worker picks up the `run_research_job` task from Redis.
2. **State Update**: The worker updates the `ResearchJob` status in PostgreSQL from `queued` to `running` and sets `started_at = datetime.now()`.
3. **LLM Resolution**: The worker determines which LLM backend to use:
   - If the request included a `transient_backend` (e.g., custom API key or provider in the request body), it decrypts the provided credentials and uses them.
   - Otherwise, it queries the `LLMBackend` table to find the default LLM configuration for the specific `org_id`.
   - An `LLMClient` instance is initialized with tracking counters for tokens (in/out) and fetched sources.

---

## 3. The Engine: Iterative Research Loop

The worker delegates the core processing to `core.research.engine.run_research()`. This is the intelligent "brain" of the system, powered by the `IterResearchEngine`.

### What Happens:
1. **Planning (LLM Call 1)**: The `planner` analyzes the user's `query` and decomposes it into several specific web search queries.
2. **The Multi-Round Loop**: For `n` rounds (up to `max_rounds` specified in the job):
   - **Searching**: The `searcher` takes the sub-queries and hits a search provider (like the local SearXNG container, or external providers like Brave/Tavily). It retrieves a list of relevant URLs.
   - **Fetching**: The `fetcher` asynchronously downloads the HTML content of these URLs, stripping out boilerplate, scripts, and styling to extract plain text.
   - **Extracting (LLM Call 2)**: The `extractor` reads the plain text from the fetched URLs and extracts key facts relevant to the original query.
   - **Progress Reporting**: After each round, an `on_progress` callback is fired. This adds newly discovered URLs and extracted excerpts to an in-memory buffer, which can be queried by the polling endpoint to see partial results.
   - **Synthesis/Check (LLM Call 3)**: The `synthesizer` reviews the findings so far and determines if there are any critical gaps. If there are, it formulates new queries for the next round. If not, the loop terminates early.
3. **Final Report Generation (LLM Call 4)**: Once the loop concludes, the `synthesizer` compiles all the extracted facts into a cohesive markdown report, injecting citation markers corresponding to the fetched sources.

---

## 4. Finalization: Saving Results & Billing

Once the `run_research()` engine returns the final `ReportOutput`, the worker persists the results.

### What Happens:
1. **Report Storage**: A new `Report` row is created in PostgreSQL. It stores the generated markdown content, a brief summary, and a JSON array of citations.
2. **Source Storage**: All URLs that were actually used and cited in the report are written to the `Source` table. This allows users to view the exact text excerpts that led to specific claims.
3. **Job Completion**: The `ResearchJob` status is updated to `completed`, and `finished_at` is set.
4. **Usage Tracking**: A `UsageRecord` row is created, capturing the total `tokens_in`, `tokens_out`, `sources_fetched`, and `duration_seconds`. This is crucial for rate-limiting, cost analysis, and billing.

---

## 5. Delivery: Webhook Dispatch

If the tenant has configured webhooks, the system pushes the result back to them, rather than forcing them to poll.

### What Happens:
1. **Webhook Resolution**: The worker looks up all registered `WebhookEndpoint` rows for the `org_id`.
2. **Payload Construction**: A standard JSON payload is built, containing the `job_id`, `status` (`completed` or `failed`), `report_url`, and original `metadata`.
3. **Signing**: To ensure security, an HMAC-SHA256 signature is generated using the payload and the customer's webhook secret. This is attached as the `X-Signature` header.
4. **Delivery Queueing**: The worker enqueues a `deliver_webhook_job` task to `arq`.
5. **HTTP Dispatch & Retry**: Another worker task picks up the `deliver_webhook_job` and performs an HTTP POST. If the customer's server is down or returns a 5xx error, the worker will automatically retry up to 5 times with exponential backoff (e.g., 10s, 30s, 120s, 600s, 3600s).

---

## Summary of the Flow

1. **User** -> `POST /v1/research` -> **FastAPI** -> Enqueues Job -> Responds `202 Accepted`
2. **Redis** -> Task -> **ARQ Worker** -> Updates Job to `running`
3. **ARQ Worker** -> `run_research()` Engine
   - *Loop*: Plan Queries -> Search Web -> Fetch HTML -> Extract Facts
4. **Engine** -> Formats Markdown Report -> Returns to Worker
5. **ARQ Worker** -> Saves Report, Sources, Usage to **PostgreSQL** -> Updates Job to `completed`
6. **ARQ Worker** -> Triggers `fire_webhook()` -> Enqueues HTTP delivery
7. **Webhook Worker** -> HTTP POST to **Customer Endpoint** (with Retries)

This asynchronous, queue-based design ensures the API is extremely resilient. The web server is never blocked by long-running LLM calls, and transient errors (like a search engine timeout or customer webhook downtime) are gracefully handled via retries.
