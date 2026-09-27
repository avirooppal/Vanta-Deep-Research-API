# Vanta API Reference & Endpoints

Base URL: `http://localhost:8000` (Local) or your Cloud URL (e.g. `https://your-app.onrender.com`).

All protected endpoints accept your LLM API Key via standard Bearer authorization:
```http
Authorization: Bearer <your-llm-api-key>
```
*(OpenAI `sk-...`, Anthropic `sk-ant-...`, Google Gemini `AIza...`, OpenRouter `sk-or-...`, Groq `gsk_...`, or Cerebras `csk-...`).*

---

## Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/v1/research` | Submit a deep research job |
| `GET` | `/v1/research/{id}` | Poll job status, progress, and report |
| `GET` | `/v1/research/{id}/stream` | Server-Sent Events (SSE) live progress stream |
| `DELETE` | `/v1/research/{id}` | Cancel an active research job |
| `POST` | `/v1/research/{id}/chat` | Grounded post-report conversational Q&A |
| `GET` | `/v1/reports/{id}/export` | Export report as Markdown, JSON, or PDF |
| `GET` | `/v1/sources` | Search and filter fetched sources |
| `GET` | `/health` | Liveness check |
| `GET` | `/health/ready` | Readiness check (DB & Redis ping) |
| `GET` | `/metrics` | Prometheus telemetry metrics |

---

## 1. Submit Research Job

`POST /v1/research`

### Request Body:
```json
{
  "query": "What are the latest breakthroughs in room-temperature superconductors?",
  "mode": "research",
  "max_rounds": 3,
  "provider": "openai",
  "model": "gpt-4o"
}
```

### Response (`202 Accepted`):
```json
{
  "id": "job_01h8a9bcde12",
  "status": "queued",
  "created_at": "2026-09-27T10:00:00Z"
}
```

---

## 2. Poll Research Job

`GET /v1/research/{id}`

### Response:
```json
{
  "id": "job_01h8a9bcde12",
  "status": "completed",
  "progress_pct": 100,
  "duration_seconds": 42,
  "report": {
    "summary": "Executive overview of findings...",
    "body_md": "# Full Research Report\n\n...",
    "citations": [
      {
        "url": "https://example.com/paper",
        "title": "Room Temperature Superconductivity Analysis",
        "trust_score": 92
      }
    ]
  }
}
```

---

## 3. Server-Sent Events (SSE) Stream

`GET /v1/research/{id}/stream`

Streams live progress updates as research unfolds across rounds:
```text
event: progress
data: {"progress_pct": 25, "active_stage": "search", "sources_found": 8}

event: complete
data: {"job_id": "job_01h8a9bcde12", "status": "completed"}
```

---

## 4. Export Report

`GET /v1/reports/{id}/export?format=pdf`

Query parameters:
- `format`: `md` | `json` | `pdf`
