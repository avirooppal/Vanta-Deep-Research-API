# Vanta Database & Schema Design

Vanta uses **PostgreSQL 16** with the **`pgvector`** extension to persist research state, atomic facts, and vector embeddings for semantic recall.

---

## Entity-Relationship Diagram

```mermaid
erDiagram
    research_jobs {
        string id PK "job_<12hex>"
        text query
        string status "queued | running | completed | failed | cancelled"
        int max_rounds "1-5"
        int progress_pct "0-100"
        text error "nullable"
        text metadata_json "Encrypted credentials & config"
        datetime created_at
        datetime finished_at
    }

    reports {
        string id PK "rpt_<12hex>"
        string job_id FK
        text summary
        text content_md
        text content_json "Citations & metadata"
        datetime created_at
    }

    sources {
        string id PK "src_<12hex>"
        string job_id FK
        text url
        text title
        int trust_score "0-100"
        datetime fetched_at
    }

    claims {
        string id PK "clm_<12hex>"
        string job_id FK
        string source_id FK
        text fact
        vector embedding "Vector(1536) pgvector"
        int trust_score
        string contradicts_claim_id FK
        datetime created_at
    }

    research_jobs ||--o{ sources : "fetches"
    research_jobs ||--o{ claims : "extracts"
    research_jobs ||--o| reports : "synthesizes"
    sources ||--o{ claims : "supports"
    claims ||--o| claims : "contradicts"
```

---

## Running Migrations

Database schema migrations are managed via Alembic:

```bash
# Upgrade to latest revision
uv run python scripts/migrate.py
```
