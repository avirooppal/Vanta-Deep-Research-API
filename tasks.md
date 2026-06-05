# Deep Research API — MVP Build Plan

> Each task is a single unit of work with one concern, a clear start state, a clear end state, and an explicit test to verify completion before moving to the next task.
> Pass tasks one at a time to your engineering LLM. Do not proceed to the next task until the test passes.

---

## Phase 0 — Project scaffold

---

### Task 0.1 — Initialize the repo and Python project

**Start state:** Empty directory.

**What to do:**
Create the following at the repo root:

- `pyproject.toml` with project name `deep-research-api`, Python `>=3.11`
- `requirements.txt` with these packages pinned:
  ```
  fastapi==0.111.0
  uvicorn[standard]==0.29.0
  sqlalchemy[asyncio]==2.0.30
  asyncpg==0.29.0
  alembic==1.13.1
  redis==5.0.4
  arq==0.25.0
  httpx==0.27.0
  pydantic==2.7.1
  pydantic-settings==2.2.1
  python-dotenv==1.0.1
  bcrypt==4.1.3
  cryptography==42.0.7
  pytest==8.2.0
  pytest-asyncio==0.23.6
  pytest-httpx==0.30.0
  ```
- `.env.example` with keys: `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `ENVIRONMENT`
- `.gitignore` ignoring `.env`, `__pycache__`, `*.pyc`, `.pytest_cache`, `data/`
- Empty directories: `api/`, `core/`, `db/`, `tests/unit/`, `tests/integration/`, `deploy/`
- `api/__init__.py`, `core/__init__.py`, `db/__init__.py`

**End state:** `pip install -r requirements.txt` completes without error.

**Test:**

```bash
python -c "import fastapi, sqlalchemy, arq, redis, httpx; print('OK')"
```

Expected output: `OK`

---

### Task 0.2 — Create the settings module

**Start state:** Task 0.1 complete.

**What to do:**
Create `core/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    secret_key: str
    environment: str = "development"
    max_research_rounds: int = 3
    extraction_concurrency: int = 3
    webhook_max_retries: int = 5
    audit_retention_days: int = 365
    export_cache_ttl_seconds: int = 86400

    class Config:
        env_file = ".env"

settings = Settings()
```

Create `.env` (not committed) with real local values for `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`.

**End state:** Settings load without error from `.env`.

**Test:**

```bash
python -c "from core.config import settings; print(settings.environment)"
```

Expected output: `development`

---

### Task 0.3 — Create the database engine and session factory

**Start state:** Task 0.2 complete. A PostgreSQL database is running and accessible at `DATABASE_URL`.

**What to do:**
Create `db/engine.py`:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass
```

Create `db/session.py`:

```python
from contextlib import asynccontextmanager
from db.engine import AsyncSessionLocal

@asynccontextmanager
async def get_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**End state:** Engine connects to PostgreSQL.

**Test:**

```python
# tests/unit/test_db_engine.py
import pytest
import pytest_asyncio
from sqlalchemy import text
from db.engine import engine

@pytest.mark.asyncio
async def test_db_connects():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
```

Run: `pytest tests/unit/test_db_engine.py -v`

---

### Task 0.4 — Create the Org model and first Alembic migration

**Start state:** Task 0.3 complete.

**What to do:**
Create `db/models/__init__.py` (empty).

Create `db/models/org.py`:

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Boolean
from datetime import datetime, timezone
from db.engine import Base

class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
```

Initialize Alembic:

```bash
alembic init db/migrations
```

Edit `alembic.ini` to set `script_location = db/migrations`.

Edit `db/migrations/env.py` to use the async engine and import `Base` and `Org`:

```python
from db.engine import Base
from db.models.org import Org  # noqa: F401 — must import for autogenerate
target_metadata = Base.metadata
```

Generate and apply the first migration:

```bash
alembic revision --autogenerate -m "create_orgs_table"
alembic upgrade head
```

**End state:** `orgs` table exists in the database.

**Test:**

```bash
python -c "
import asyncio
from sqlalchemy import text
from db.engine import engine

async def check():
    async with engine.connect() as conn:
        r = await conn.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_name='orgs'\"))
        assert r.scalar() == 'orgs', 'orgs table not found'
        print('OK')

asyncio.run(check())
"
```

---

### Task 0.5 — Create the APIKey model and migration

**Start state:** Task 0.4 complete.

**What to do:**
Create `db/models/api_key.py`:

```python
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Boolean, ForeignKey
from datetime import datetime, timezone
from db.engine import Base

class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(String, ForeignKey("orgs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    key_hash: Mapped[str] = mapped_column(String, nullable=False)
    scope: Mapped[str] = mapped_column(String, default="research:write,research:read")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Add the import to `db/migrations/env.py`:

```python
from db.models.api_key import APIKey  # noqa: F401
```

Generate and apply:

```bash
alembic revision --autogenerate -m "create_api_keys_table"
alembic upgrade head
```

**End state:** `api_keys` table exists.

**Test:**

```bash
python -c "
import asyncio
from sqlalchemy import text
from db.engine import engine

async def check():
    async with engine.connect() as conn:
        r = await conn.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_name='api_keys'\"))
        assert r.scalar() == 'api_keys'
        print('OK')

asyncio.run(check())
"
```

---

### Task 0.6 — Create the ResearchJob model and migration

**Start state:** Task 0.5 complete.

**What to do:**
Create `db/models/research_job.py`:

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey
from datetime import datetime, timezone
from typing import Optional
from db.engine import Base

class ResearchJob(Base):
    __tablename__ = "research_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(String, ForeignKey("orgs.id"), nullable=False)
    api_key_id: Mapped[str] = mapped_column(String, ForeignKey("api_keys.id"), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="queued")
    priority: Mapped[int] = mapped_column(Integer, default=3)
    max_rounds: Mapped[int] = mapped_column(Integer, default=3)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model_override: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

Add import to `env.py`, generate and apply migration.

**End state:** `research_jobs` table exists.

**Test:** Same pattern as Task 0.5, check for `research_jobs`.

---

### Task 0.7 — Create the Report and Source models and migration

**Start state:** Task 0.6 complete.

**What to do:**
Create `db/models/report.py`:

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Text, ForeignKey
from datetime import datetime, timezone
from typing import Optional
from db.engine import Base

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("research_jobs.id"), nullable=False, unique=True)
    org_id: Mapped[str] = mapped_column(String, ForeignKey("orgs.id"), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

Create `db/models/source.py`:

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Text, ForeignKey, Integer
from datetime import datetime, timezone
from typing import Optional
from db.engine import Base

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("research_jobs.id"), nullable=False)
    org_id: Mapped[str] = mapped_column(String, ForeignKey("orgs.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

Add imports, generate and apply migration.

**End state:** `reports` and `sources` tables exist.

**Test:** Check both table names exist via `information_schema.tables`.

---

### Task 0.8 — Create the AuditLog and UsageRecord models and migration

**Start state:** Task 0.7 complete.

**What to do:**
Create `db/models/audit_log.py`:

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey
from datetime import datetime, timezone
from typing import Optional
from db.engine import Base

class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    api_key_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    method: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)
    query_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
```

Create `db/models/usage_record.py`:

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, ForeignKey
from datetime import datetime, timezone
from db.engine import Base

class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("research_jobs.id"), nullable=False, unique=True)
    org_id: Mapped[str] = mapped_column(String, ForeignKey("orgs.id"), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    sources_fetched: Mapped[int] = mapped_column(Integer, default=0)
    search_queries_issued: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

Add imports, generate and apply migration.

**End state:** `audit_log` and `usage_records` tables exist.

**Test:** Check both table names.

---

### Task 0.9 — Create the LLMBackend model and migration

**Start state:** Task 0.8 complete.

**What to do:**
Create `db/models/llm_backend.py`:

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Integer, LargeBinary, ForeignKey
from db.engine import Base

class LLMBackend(Base):
    __tablename__ = "llm_backends"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    org_id: Mapped[str] = mapped_column(String, ForeignKey("orgs.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str] = mapped_column(String, nullable=False)
    api_key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    max_concurrent: Mapped[int] = mapped_column(Integer, default=3)
```

Add import, generate and apply migration.

**End state:** `llm_backends` table exists.

**Test:** Check table name.

---

## Phase 1 — Security layer

---

### Task 1.1 — Implement Fernet encryption utility

**Start state:** Phase 0 complete.

**What to do:**
Create `core/security/encryption.py`:

```python
import base64
import os
from cryptography.fernet import Fernet
from core.config import settings

def _get_fernet() -> Fernet:
    # Derive a 32-byte key from SECRET_KEY
    import hashlib
    key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)

def encrypt(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode())

def decrypt(ciphertext: bytes) -> str:
    return _get_fernet().decrypt(ciphertext).decode()
```

Create `core/security/__init__.py` (empty).

**End state:** Encrypt/decrypt roundtrip works.

**Test:**

```python
# tests/unit/test_encryption.py
from core.security.encryption import encrypt, decrypt

def test_roundtrip():
    plaintext = "sk-my-secret-api-key-12345"
    ciphertext = encrypt(plaintext)
    assert isinstance(ciphertext, bytes)
    assert decrypt(ciphertext) == plaintext

def test_ciphertext_differs_from_plaintext():
    result = encrypt("hello")
    assert result != b"hello"
```

Run: `pytest tests/unit/test_encryption.py -v`

---

### Task 1.2 — Implement API key generation and hashing

**Start state:** Task 1.1 complete.

**What to do:**
Create `core/security/api_keys.py`:

```python
import secrets
import bcrypt

PREFIX = "drapi_live_"

def generate_api_key(org_prefix: str) -> tuple[str, str]:
    """
    Returns (full_key, key_hash).
    full_key is shown to the user once and never stored.
    key_hash is stored in the database.
    """
    secret = secrets.token_hex(32)
    full_key = f"{PREFIX}{org_prefix[:8]}_{secret}"
    key_hash = bcrypt.hashpw(full_key.encode(), bcrypt.gensalt()).decode()
    return full_key, key_hash

def verify_api_key(full_key: str, key_hash: str) -> bool:
    return bcrypt.checkpw(full_key.encode(), key_hash.encode())
```

**End state:** Key generation and verification work correctly.

**Test:**

```python
# tests/unit/test_api_keys.py
from core.security.api_keys import generate_api_key, verify_api_key, PREFIX

def test_key_has_prefix():
    full_key, _ = generate_api_key("orgabc123")
    assert full_key.startswith(PREFIX)

def test_verify_correct_key():
    full_key, key_hash = generate_api_key("orgabc123")
    assert verify_api_key(full_key, key_hash) is True

def test_verify_wrong_key():
    _, key_hash = generate_api_key("orgabc123")
    assert verify_api_key("drapi_live_wrong_key", key_hash) is False

def test_two_keys_are_unique():
    key1, _ = generate_api_key("orgabc123")
    key2, _ = generate_api_key("orgabc123")
    assert key1 != key2
```

Run: `pytest tests/unit/test_api_keys.py -v`

---

### Task 1.3 — Implement auth middleware

**Start state:** Task 1.2 complete.

**What to do:**
Create `api/middleware/__init__.py` (empty).

Create `api/middleware/auth.py`:

```python
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from db.session import get_db_session
from db.models.api_key import APIKey
from db.models.org import Org
from core.security.api_keys import verify_api_key

async def auth_middleware(request: Request, call_next):
    # Skip auth for health and docs endpoints
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "Missing or invalid Authorization header"})

    presented_key = auth_header.removeprefix("Bearer ").strip()

    async with get_db_session() as db:
        # Fetch all active keys for candidate matching
        # In production this is cached; for MVP a DB lookup per request is acceptable
        result = await db.execute(
            select(APIKey).where(APIKey.is_active == True)
        )
        keys = result.scalars().all()

    matched_key = None
    for key in keys:
        if verify_api_key(presented_key, key.key_hash):
            matched_key = key
            break

    if not matched_key:
        return JSONResponse(status_code=401, content={"error": "Invalid API key"})

    async with get_db_session() as db:
        org = await db.get(Org, matched_key.org_id)

    if not org or not org.is_active:
        return JSONResponse(status_code=403, content={"error": "Organisation inactive"})

    request.state.org_id = matched_key.org_id
    request.state.api_key_id = matched_key.id
    request.state.scope = matched_key.scope

    return await call_next(request)
```

**End state:** Module importable without error.

**Test:**

```python
# tests/unit/test_auth_middleware.py
from core.security.api_keys import generate_api_key, verify_api_key

def test_verify_logic_used_in_middleware():
    full_key, key_hash = generate_api_key("testorg1")
    assert verify_api_key(full_key, key_hash)
    assert not verify_api_key("drapi_live_bad_key_000", key_hash)
```

Run: `pytest tests/unit/test_auth_middleware.py -v`

---

### Task 1.4 — Implement audit log middleware

**Start state:** Task 1.3 complete.

**What to do:**
Create `api/middleware/audit_log.py`:

```python
import time
import uuid
from fastapi import Request
from db.session import get_db_session
from db.models.audit_log import AuditLog

async def audit_log_middleware(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)

    org_id = getattr(request.state, "org_id", None)
    api_key_id = getattr(request.state, "api_key_id", None)

    # Extract query text for research submissions only
    query_text = None
    if request.url.path == "/v1/research" and request.method == "POST":
        # Body already consumed by this point; query_text set by route handler
        query_text = getattr(request.state, "query_text", None)

    try:
        async with get_db_session() as db:
            log = AuditLog(
                org_id=org_id,
                api_key_id=api_key_id,
                method=request.method,
                path=request.url.path,
                query_text=query_text,
                response_status=response.status_code,
                duration_ms=duration_ms,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
            db.add(log)
    except Exception:
        pass  # Audit failure must never break the request

    return response
```

**End state:** Module importable without error.

**Test:**

```python
# tests/unit/test_audit_log_middleware.py
import importlib

def test_module_importable():
    import api.middleware.audit_log
    assert hasattr(api.middleware.audit_log, "audit_log_middleware")
```

Run: `pytest tests/unit/test_audit_log_middleware.py -v`

---

### Task 1.5 — Wire middleware into the FastAPI app

**Start state:** Task 1.4 complete.

**What to do:**
Create `api/app.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from db.engine import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

app = FastAPI(
    title="Deep Research API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

from api.middleware.auth import auth_middleware
from api.middleware.audit_log import audit_log_middleware
from starlette.middleware.base import BaseHTTPMiddleware

app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=audit_log_middleware)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

Create `api/__init__.py` (empty).

**End state:** App starts and `/health` is reachable.

**Test:**

```bash
uvicorn api.app:app --port 8000 &
sleep 2
curl -s http://localhost:8000/health
# Expected: {"status":"ok"}
kill %1
```

---

## Phase 2 — LLM client

---

### Task 2.1 — Define LLM client interfaces and data types

**Start state:** Phase 1 complete.

**What to do:**
Create `core/llm/__init__.py` (empty).

Create `core/llm/types.py`:

```python
from dataclasses import dataclass, field
from typing import AsyncIterator

@dataclass
class Message:
    role: str   # "system" | "user" | "assistant"
    content: str

@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_in: int
    tokens_out: int

@dataclass
class LLMConfig:
    provider: str        # openai | anthropic | ollama | openai_compatible
    base_url: str
    api_key: str | None
    model: str
    max_concurrent: int = 3
    temperature: float = 0.2
    max_tokens: int = 4096
```

**End state:** Types importable without error.

**Test:**

```python
# tests/unit/test_llm_types.py
from core.llm.types import Message, LLMResponse, LLMConfig

def test_message_creation():
    m = Message(role="user", content="hello")
    assert m.role == "user"

def test_llm_config_defaults():
    cfg = LLMConfig(provider="openai", base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")
    assert cfg.temperature == 0.2
    assert cfg.max_concurrent == 3
```

Run: `pytest tests/unit/test_llm_types.py -v`

---

### Task 2.2 — Implement the OpenAI provider

**Start state:** Task 2.1 complete.

**What to do:**
Create `core/llm/providers/__init__.py` (empty).

Create `core/llm/providers/openai.py`:

```python
import httpx
from core.llm.types import Message, LLMResponse, LLMConfig

async def call_openai(messages: list[Message], config: LLMConfig) -> LLMResponse:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    payload = {
        "model": config.model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{config.base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    return LLMResponse(
        content=data["choices"][0]["message"]["content"],
        model=data.get("model", config.model),
        tokens_in=data.get("usage", {}).get("prompt_tokens", 0),
        tokens_out=data.get("usage", {}).get("completion_tokens", 0),
    )
```

**End state:** Provider function defined and importable.

**Test:**

```python
# tests/unit/test_openai_provider.py
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_call_openai_parses_response():
    from core.llm.providers.openai import call_openai
    from core.llm.types import Message, LLMConfig

    mock_response = {
        "choices": [{"message": {"content": "Test response"}}],
        "model": "gpt-4o",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = AsyncMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = lambda: None
        mock_post.return_value = mock_resp

        config = LLMConfig(provider="openai", base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")
        result = await call_openai([Message(role="user", content="hi")], config)

    assert result.content == "Test response"
    assert result.tokens_in == 10
    assert result.tokens_out == 5
```

Run: `pytest tests/unit/test_openai_provider.py -v`

---

### Task 2.3 — Implement the Anthropic provider

**Start state:** Task 2.2 complete. Add `anthropic==0.26.0` to `requirements.txt` and install.

**What to do:**
Create `core/llm/providers/anthropic.py`:

```python
import httpx
from core.llm.types import Message, LLMResponse, LLMConfig

async def call_anthropic(messages: list[Message], config: LLMConfig) -> LLMResponse:
    system_messages = [m for m in messages if m.role == "system"]
    user_messages = [m for m in messages if m.role != "system"]

    system_content = system_messages[0].content if system_messages else ""

    payload = {
        "model": config.model,
        "max_tokens": config.max_tokens,
        "system": system_content,
        "messages": [{"role": m.role, "content": m.content} for m in user_messages],
    }

    headers = {
        "x-api-key": config.api_key or "",
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{config.base_url.rstrip('/')}/messages",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    return LLMResponse(
        content=data["content"][0]["text"],
        model=data.get("model", config.model),
        tokens_in=data.get("usage", {}).get("input_tokens", 0),
        tokens_out=data.get("usage", {}).get("output_tokens", 0),
    )
```

**End state:** Anthropic provider importable and response parsing correct.

**Test:**

```python
# tests/unit/test_anthropic_provider.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_call_anthropic_parses_response():
    from core.llm.providers.anthropic import call_anthropic
    from core.llm.types import Message, LLMConfig

    mock_response = {
        "content": [{"type": "text", "text": "Anthropic response"}],
        "model": "claude-sonnet-4-6",
        "usage": {"input_tokens": 20, "output_tokens": 8},
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = AsyncMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = lambda: None
        mock_post.return_value = mock_resp

        config = LLMConfig(
            provider="anthropic",
            base_url="https://api.anthropic.com/v1",
            api_key="sk-ant-test",
            model="claude-sonnet-4-6",
        )
        result = await call_anthropic([Message(role="user", content="hello")], config)

    assert result.content == "Anthropic response"
    assert result.tokens_in == 20
```

Run: `pytest tests/unit/test_anthropic_provider.py -v`

---

### Task 2.4 — Implement the unified LLMClient

**Start state:** Task 2.3 complete.

**What to do:**
Create `core/llm/client.py`:

```python
from core.llm.types import Message, LLMResponse, LLMConfig
from core.llm.providers.openai import call_openai
from core.llm.providers.anthropic import call_anthropic

class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config

    async def complete(self, messages: list[Message]) -> LLMResponse:
        provider = self.config.provider

        if provider in ("openai", "openai_compatible", "azure_openai"):
            return await call_openai(messages, self.config)
        elif provider == "anthropic":
            return await call_anthropic(messages, self.config)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @classmethod
    def from_backend(cls, backend) -> "LLMClient":
        from core.security.encryption import decrypt
        api_key = decrypt(backend.api_key_encrypted) if backend.api_key_encrypted else None
        config = LLMConfig(
            provider=backend.provider,
            base_url=backend.base_url,
            api_key=api_key,
            model=backend.model,
            max_concurrent=backend.max_concurrent,
        )
        return cls(config)
```

**End state:** LLMClient routes to correct provider.

**Test:**

```python
# tests/unit/test_llm_client.py
import pytest
from unittest.mock import AsyncMock, patch
from core.llm.client import LLMClient
from core.llm.types import LLMConfig, Message, LLMResponse

@pytest.mark.asyncio
async def test_routes_to_openai():
    config = LLMConfig(provider="openai", base_url="https://api.openai.com/v1", api_key="sk-test", model="gpt-4o")
    client = LLMClient(config)

    mock_result = LLMResponse(content="mocked", model="gpt-4o", tokens_in=5, tokens_out=3)
    with patch("core.llm.providers.openai.call_openai", new_callable=AsyncMock, return_value=mock_result):
        result = await client.complete([Message(role="user", content="hi")])
    assert result.content == "mocked"

@pytest.mark.asyncio
async def test_raises_on_unknown_provider():
    config = LLMConfig(provider="unknown_provider", base_url="http://x", api_key=None, model="m")
    client = LLMClient(config)
    with pytest.raises(ValueError, match="Unsupported provider"):
        await client.complete([Message(role="user", content="hi")])
```

Run: `pytest tests/unit/test_llm_client.py -v`

---

## Phase 3 — Search and fetch

---

### Task 3.1 — Implement the SearXNG search client

**Start state:** Phase 2 complete.

**What to do:**
Create `integrations/__init__.py` (empty).

Create `integrations/searxng.py`:

```python
import httpx
from dataclasses import dataclass

@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str

async def search_searxng(query: str, base_url: str, num_results: int = 10) -> list[SearchResult]:
    params = {
        "q": query,
        "format": "json",
        "engines": "google,bing,duckduckgo",
        "language": "en",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{base_url.rstrip('/')}/search", params=params)
        response.raise_for_status()
        data = response.json()

    results = []
    for item in data.get("results", [])[:num_results]:
        results.append(SearchResult(
            url=item.get("url", ""),
            title=item.get("title", ""),
            snippet=item.get("content", ""),
        ))
    return results
```

**End state:** SearXNG client parses response correctly.

**Test:**

```python
# tests/unit/test_searxng.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_searxng_parses_results():
    from integrations.searxng import search_searxng

    mock_response = {
        "results": [
            {"url": "https://example.com", "title": "Example", "content": "An example site."},
            {"url": "https://another.com", "title": "Another", "content": "Another site."},
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = AsyncMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        results = await search_searxng("test query", "http://searxng:8080")

    assert len(results) == 2
    assert results[0].url == "https://example.com"
    assert results[0].title == "Example"

@pytest.mark.asyncio
async def test_searxng_respects_num_results():
    from integrations.searxng import search_searxng

    mock_response = {"results": [{"url": f"https://example{i}.com", "title": f"Ex{i}", "content": "c"} for i in range(10)]}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = AsyncMock()
        mock_resp.json.return_value = mock_response
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        results = await search_searxng("query", "http://searxng:8080", num_results=3)

    assert len(results) == 3
```

Run: `pytest tests/unit/test_searxng.py -v`

---

### Task 3.2 — Implement the URL content fetcher

**Start state:** Task 3.1 complete. Add `beautifulsoup4==4.12.3` and `lxml==5.2.1` to `requirements.txt` and install.

**What to do:**
Create `integrations/fetcher.py`:

```python
import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass

MAX_CONTENT_CHARS = 12000

@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    success: bool
    error: str | None = None

async def fetch_url(url: str) -> FetchedPage:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DeepResearchBot/1.0)"
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Remove boilerplate tags
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title else ""
        text = " ".join(soup.get_text(separator=" ").split())
        text = text[:MAX_CONTENT_CHARS]

        return FetchedPage(url=url, title=title, text=text, success=True)

    except Exception as exc:
        return FetchedPage(url=url, title="", text="", success=False, error=str(exc))
```

**End state:** Fetcher returns cleaned text from HTML.

**Test:**

```python
# tests/unit/test_fetcher.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_fetch_extracts_text():
    from integrations.fetcher import fetch_url

    html = "<html><head><title>Test Page</title></head><body><p>Hello world content.</p><script>ignored</script></body></html>"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        page = await fetch_url("https://example.com")

    assert page.success is True
    assert "Hello world content" in page.text
    assert "ignored" not in page.text
    assert page.title == "Test Page"

@pytest.mark.asyncio
async def test_fetch_handles_error():
    from integrations.fetcher import fetch_url
    import httpx

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("timeout")):
        page = await fetch_url("https://unreachable.example.com")

    assert page.success is False
    assert page.error is not None
```

Run: `pytest tests/unit/test_fetcher.py -v`

---

## Phase 4 — Research engine

---

### Task 4.1 — Implement the query planner

**Start state:** Phase 3 complete.

**What to do:**
Create `core/research/__init__.py` (empty).

Create `core/research/planner.py`:

```python
import json
from core.llm.client import LLMClient
from core.llm.types import Message

PLAN_PROMPT = """You are a research planning assistant.
Given a research question, generate a list of specific search queries that together would comprehensively answer it.
Return ONLY a JSON array of strings, no explanation, no markdown fences.
Example output: ["query one", "query two", "query three"]
Generate between 3 and 6 queries."""

async def plan_queries(question: str, llm: LLMClient) -> list[str]:
    messages = [
        Message(role="system", content=PLAN_PROMPT),
        Message(role="user", content=f"Research question: {question}"),
    ]
    response = await llm.complete(messages)
    try:
        queries = json.loads(response.content)
        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            return queries[:6]
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: treat the whole question as one query
    return [question]
```

**End state:** Planner returns a list of strings.

**Test:**

```python
# tests/unit/test_planner.py
import pytest
from unittest.mock import AsyncMock
from core.research.planner import plan_queries
from core.llm.types import LLMResponse

@pytest.mark.asyncio
async def test_plan_queries_parses_json():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content='["query one", "query two", "query three"]',
        model="gpt-4o", tokens_in=10, tokens_out=10
    )
    queries = await plan_queries("What is X?", mock_llm)
    assert queries == ["query one", "query two", "query three"]

@pytest.mark.asyncio
async def test_plan_queries_fallback_on_bad_json():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content="not valid json at all",
        model="gpt-4o", tokens_in=5, tokens_out=5
    )
    queries = await plan_queries("What is X?", mock_llm)
    assert queries == ["What is X?"]

@pytest.mark.asyncio
async def test_plan_queries_caps_at_six():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content='["q1","q2","q3","q4","q5","q6","q7","q8"]',
        model="gpt-4o", tokens_in=10, tokens_out=10
    )
    queries = await plan_queries("Big question", mock_llm)
    assert len(queries) <= 6
```

Run: `pytest tests/unit/test_planner.py -v`

---

### Task 4.2 — Implement the content extractor

**Start state:** Task 4.1 complete.

**What to do:**
Create `core/research/extractor.py`:

```python
from dataclasses import dataclass
from core.llm.client import LLMClient
from core.llm.types import Message
from integrations.fetcher import FetchedPage

@dataclass
class Finding:
    url: str
    title: str
    facts: str      # LLM-extracted key facts
    round_number: int

EXTRACT_PROMPT = """You are a research assistant extracting key facts from a web page.
Given the page content below, extract only the facts relevant to the research question.
Be concise. Return plain text bullet points. Maximum 300 words.
If the page has no relevant content, return: NO_RELEVANT_CONTENT"""

async def extract_findings(
    page: FetchedPage,
    question: str,
    llm: LLMClient,
    round_number: int = 1,
) -> Finding | None:
    if not page.success or not page.text:
        return None

    messages = [
        Message(role="system", content=EXTRACT_PROMPT),
        Message(
            role="user",
            content=f"Research question: {question}\n\n<<<PAGE CONTENT>>>\n{page.text[:8000]}\n<<<END PAGE CONTENT>>>",
        ),
    ]
    response = await llm.complete(messages)

    if "NO_RELEVANT_CONTENT" in response.content:
        return None

    return Finding(
        url=page.url,
        title=page.title,
        facts=response.content.strip(),
        round_number=round_number,
    )
```

**End state:** Extractor returns `Finding` or `None`.

**Test:**

```python
# tests/unit/test_extractor.py
import pytest
from unittest.mock import AsyncMock
from core.research.extractor import extract_findings
from core.llm.types import LLMResponse
from integrations.fetcher import FetchedPage

@pytest.mark.asyncio
async def test_extracts_facts_from_page():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content="- Fact one\n- Fact two", model="gpt-4o", tokens_in=50, tokens_out=20
    )
    page = FetchedPage(url="https://ex.com", title="Ex", text="Some content", success=True)
    finding = await extract_findings(page, "What is X?", mock_llm)
    assert finding is not None
    assert finding.url == "https://ex.com"
    assert "Fact one" in finding.facts

@pytest.mark.asyncio
async def test_returns_none_for_no_relevant_content():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content="NO_RELEVANT_CONTENT", model="gpt-4o", tokens_in=30, tokens_out=5
    )
    page = FetchedPage(url="https://ex.com", title="Ex", text="Off-topic content", success=True)
    finding = await extract_findings(page, "What is X?", mock_llm)
    assert finding is None

@pytest.mark.asyncio
async def test_returns_none_for_failed_fetch():
    mock_llm = AsyncMock()
    page = FetchedPage(url="https://ex.com", title="", text="", success=False, error="timeout")
    finding = await extract_findings(page, "What is X?", mock_llm)
    assert finding is None
    mock_llm.complete.assert_not_called()
```

Run: `pytest tests/unit/test_extractor.py -v`

---

### Task 4.3 — Implement the synthesizer

**Start state:** Task 4.2 complete.

**What to do:**
Create `core/research/synthesizer.py`:

```python
import json
from dataclasses import dataclass
from core.llm.client import LLMClient
from core.llm.types import Message
from core.research.extractor import Finding

@dataclass
class ReportOutput:
    query: str
    summary: str
    body_md: str
    citations: list[dict]   # [{"id": "src_1", "url": "...", "title": "..."}]

CONTINUE_PROMPT = """You are evaluating whether a research task needs more investigation.
Given the findings so far and the original question, reply with ONLY the word CONTINUE or DONE.
Reply CONTINUE if important aspects are uncovered or unclear.
Reply DONE if the findings are comprehensive enough to write a full report."""

SYNTHESIS_PROMPT = """You are a senior research analyst writing a comprehensive research report.
Given the question and collected findings below, write a well-structured markdown report.

Requirements:
- Start with a 2-3 sentence executive summary
- Use ## headings for major sections
- Include inline citation markers like [1], [2] referencing the sources list
- Be factual, cite sources for all claims
- Minimum 500 words
- End with a ## Sources section listing all cited sources

Return ONLY the markdown report."""

async def should_continue(
    question: str, findings: list[Finding], llm: LLMClient
) -> bool:
    findings_text = "\n\n".join(
        f"Source: {f.url}\n{f.facts}" for f in findings
    )
    messages = [
        Message(role="system", content=CONTINUE_PROMPT),
        Message(
            role="user",
            content=f"Question: {question}\n\nFindings so far:\n{findings_text[:6000]}",
        ),
    ]
    response = await llm.complete(messages)
    return "CONTINUE" in response.content.upper()

async def synthesize_report(
    question: str, findings: list[Finding], llm: LLMClient
) -> ReportOutput:
    findings_text = "\n\n".join(
        f"[{i+1}] {f.url}\n{f.facts}" for i, f in enumerate(findings)
    )
    messages = [
        Message(role="system", content=SYNTHESIS_PROMPT),
        Message(
            role="user",
            content=f"Research question: {question}\n\nFindings:\n{findings_text}",
        ),
    ]
    response = await llm.complete(messages)
    body_md = response.content.strip()
    summary = body_md.split("\n\n")[0].lstrip("#").strip()

    citations = [
        {"id": f"src_{i+1}", "url": f.url, "title": f.title}
        for i, f in enumerate(findings)
    ]

    return ReportOutput(
        query=question,
        summary=summary,
        body_md=body_md,
        citations=citations,
    )
```

**End state:** Synthesizer returns a `ReportOutput`.

**Test:**

```python
# tests/unit/test_synthesizer.py
import pytest
from unittest.mock import AsyncMock
from core.research.synthesizer import should_continue, synthesize_report
from core.research.extractor import Finding
from core.llm.types import LLMResponse

SAMPLE_FINDINGS = [
    Finding(url="https://a.com", title="Source A", facts="Fact one about X.", round_number=1),
    Finding(url="https://b.com", title="Source B", facts="Fact two about X.", round_number=1),
]

@pytest.mark.asyncio
async def test_should_continue_true():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(content="CONTINUE", model="gpt-4o", tokens_in=10, tokens_out=1)
    result = await should_continue("What is X?", SAMPLE_FINDINGS, mock_llm)
    assert result is True

@pytest.mark.asyncio
async def test_should_continue_false():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(content="DONE", model="gpt-4o", tokens_in=10, tokens_out=1)
    result = await should_continue("What is X?", SAMPLE_FINDINGS, mock_llm)
    assert result is False

@pytest.mark.asyncio
async def test_synthesize_report_structure():
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = LLMResponse(
        content="Executive summary.\n\n## Section 1\nContent [1]\n\n## Sources\n[1] https://a.com",
        model="gpt-4o", tokens_in=100, tokens_out=50
    )
    report = await synthesize_report("What is X?", SAMPLE_FINDINGS, mock_llm)
    assert report.query == "What is X?"
    assert len(report.citations) == 2
    assert report.citations[0]["url"] == "https://a.com"
    assert "Executive summary" in report.summary
```

Run: `pytest tests/unit/test_synthesizer.py -v`

---

### Task 4.4 — Implement the IterResearch engine

**Start state:** Task 4.3 complete.

**What to do:**
Create `core/research/engine.py`:

```python
import asyncio
from dataclasses import dataclass, field
from typing import Callable, Awaitable
from core.llm.client import LLMClient
from core.research.planner import plan_queries
from core.research.extractor import extract_findings, Finding
from core.research.synthesizer import should_continue, synthesize_report, ReportOutput
from integrations.searxng import search_searxng, SearchResult
from integrations.fetcher import fetch_url
from core.config import settings

@dataclass
class RoundResult:
    round_number: int
    new_findings: list[Finding]
    total_findings: int

ProgressCallback = Callable[[RoundResult], Awaitable[None]]

async def _noop_progress(result: RoundResult) -> None:
    pass

async def run_research(
    question: str,
    llm: LLMClient,
    searxng_url: str,
    max_rounds: int = 3,
    on_progress: ProgressCallback = _noop_progress,
    cancelled: asyncio.Event | None = None,
) -> ReportOutput:
    all_findings: list[Finding] = []
    sem = asyncio.Semaphore(settings.extraction_concurrency)

    for round_n in range(1, max_rounds + 1):
        if cancelled and cancelled.is_set():
            break

        queries = await plan_queries(question, llm)
        search_tasks = [search_searxng(q, searxng_url, num_results=5) for q in queries]
        search_results_nested = await asyncio.gather(*search_tasks, return_exceptions=True)

        urls: list[str] = []
        seen: set[str] = {f.url for f in all_findings}
        for result_list in search_results_nested:
            if isinstance(result_list, list):
                for r in result_list:
                    if r.url not in seen:
                        urls.append(r.url)
                        seen.add(r.url)

        async def fetch_and_extract(url: str) -> Finding | None:
            async with sem:
                page = await fetch_url(url)
                return await extract_findings(page, question, llm, round_n)

        extract_tasks = [fetch_and_extract(url) for url in urls[:15]]
        raw_findings = await asyncio.gather(*extract_tasks, return_exceptions=True)

        new_findings = [f for f in raw_findings if isinstance(f, Finding) and f is not None]
        all_findings.extend(new_findings)

        await on_progress(RoundResult(
            round_number=round_n,
            new_findings=new_findings,
            total_findings=len(all_findings),
        ))

        if all_findings and not await should_continue(question, all_findings, llm):
            break

    if not all_findings:
        return ReportOutput(
            query=question,
            summary="No findings could be gathered for this query.",
            body_md="No findings could be gathered.",
            citations=[],
        )

    return await synthesize_report(question, all_findings, llm)
```

**End state:** Engine orchestrates all components end-to-end.

**Test:**

```python
# tests/unit/test_engine.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from core.research.engine import run_research
from core.research.extractor import Finding
from core.research.synthesizer import ReportOutput
from core.llm.types import LLMResponse
from integrations.searxng import SearchResult
from integrations.fetcher import FetchedPage

@pytest.mark.asyncio
async def test_engine_returns_report():
    mock_llm = AsyncMock()
    # plan_queries returns JSON list
    # should_continue returns DONE after round 1
    # synthesize_report returns the final report
    mock_llm.complete.side_effect = [
        LLMResponse(content='["query one"]', model="gpt-4o", tokens_in=10, tokens_out=10),
        LLMResponse(content="- Fact one\n- Fact two", model="gpt-4o", tokens_in=20, tokens_out=10),
        LLMResponse(content="DONE", model="gpt-4o", tokens_in=10, tokens_out=1),
        LLMResponse(content="## Summary\nContent [1]\n\n## Sources\n[1] https://a.com", model="gpt-4o", tokens_in=100, tokens_out=50),
    ]

    mock_search_results = [SearchResult(url="https://a.com", title="A", snippet="snippet")]
    mock_page = FetchedPage(url="https://a.com", title="A", text="Content about topic.", success=True)

    with patch("core.research.engine.search_searxng", AsyncMock(return_value=mock_search_results)), \
         patch("core.research.engine.fetch_url", AsyncMock(return_value=mock_page)):
        report = await run_research("What is X?", mock_llm, "http://searxng:8080", max_rounds=2)

    assert isinstance(report, ReportOutput)
    assert report.query == "What is X?"

@pytest.mark.asyncio
async def test_engine_respects_cancellation():
    cancelled = asyncio.Event()
    cancelled.set()
    mock_llm = AsyncMock()

    report = await run_research(
        "What is X?", mock_llm, "http://searxng:8080",
        max_rounds=3, cancelled=cancelled
    )

    assert report.query == "What is X?"
    mock_llm.complete.assert_not_called()
```

Run: `pytest tests/unit/test_engine.py -v`

---

## Phase 5 — Job queue

---

### Task 5.1 — Define the ARQ worker and task

**Start state:** Phase 4 complete.

**What to do:**
Create `core/queue/__init__.py` (empty).

Create `core/queue/tasks.py`:

```python
import uuid
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from db.session import get_db_session
from db.models.research_job import ResearchJob
from db.models.report import Report
from db.models.source import Source
from db.models.usage_record import UsageRecord
from db.models.llm_backend import LLMBackend
from core.llm.client import LLMClient
from core.research.engine import run_research, RoundResult
from core.config import settings

async def run_research_job(ctx: dict, job_id: str) -> None:
    cancel_event = asyncio.Event()

    async with get_db_session() as db:
        job = await db.get(ResearchJob, job_id)
        if not job or job.status == "cancelled":
            return
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)

        backend_result = await db.execute(
            select(LLMBackend).where(
                LLMBackend.org_id == job.org_id,
                LLMBackend.is_default == True,
            )
        )
        backend = backend_result.scalar_one_or_none()
        if not backend:
            job.status = "failed"
            job.error = "No default LLM backend configured for this organisation"
            job.finished_at = datetime.now(timezone.utc)
            return

    llm = LLMClient.from_backend(backend)
    sources_buffer: list[dict] = []
    tokens_in_total = 0
    tokens_out_total = 0

    async def on_progress(result: RoundResult) -> None:
        nonlocal tokens_in_total, tokens_out_total
        for finding in result.new_findings:
            sources_buffer.append({
                "url": finding.url,
                "title": finding.title,
                "excerpt": finding.facts[:500],
                "round_number": finding.round_number,
            })

    try:
        report_output = await run_research(
            question=job.query,
            llm=llm,
            searxng_url=settings.searxng_url if hasattr(settings, "searxng_url") else "http://searxng:8080",
            max_rounds=job.max_rounds,
            on_progress=on_progress,
            cancelled=cancel_event,
        )

        async with get_db_session() as db:
            import json
            report = Report(
                id=f"rpt_{uuid.uuid4().hex[:12]}",
                job_id=job_id,
                org_id=job.org_id,
                summary=report_output.summary,
                content_md=report_output.body_md,
                content_json=json.dumps({
                    "citations": report_output.citations,
                }),
            )
            db.add(report)

            for src in sources_buffer:
                db.add(Source(
                    id=f"src_{uuid.uuid4().hex[:12]}",
                    job_id=job_id,
                    org_id=job.org_id,
                    url=src["url"],
                    title=src["title"],
                    excerpt=src["excerpt"],
                    round_number=src["round_number"],
                ))

            job_row = await db.get(ResearchJob, job_id)
            job_row.status = "completed"
            job_row.finished_at = datetime.now(timezone.utc)

    except Exception as exc:
        async with get_db_session() as db:
            job_row = await db.get(ResearchJob, job_id)
            if job_row:
                job_row.status = "failed"
                job_row.error = str(exc)[:1000]
                job_row.finished_at = datetime.now(timezone.utc)
```

Add `searxng_url: str = "http://searxng:8080"` to `core/config.py` Settings.

**End state:** Task function defined and importable.

**Test:**

```python
# tests/unit/test_tasks_importable.py
def test_task_importable():
    from core.queue.tasks import run_research_job
    assert callable(run_research_job)
```

Run: `pytest tests/unit/test_tasks_importable.py -v`

---

### Task 5.2 — Define the ARQ WorkerSettings

**Start state:** Task 5.1 complete.

**What to do:**
Create `core/queue/worker.py`:

```python
from arq.connections import RedisSettings
from core.queue.tasks import run_research_job
from core.config import settings
import redis.asyncio as aioredis

def get_redis_settings() -> RedisSettings:
    from urllib.parse import urlparse
    parsed = urlparse(settings.redis_url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
    )

class WorkerSettings:
    functions = [run_research_job]
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 600          # 10 minutes max per research job
    keep_result = 3600         # Keep results in Redis for 1 hour
```

**End state:** WorkerSettings importable.

**Test:**

```python
# tests/unit/test_worker_settings.py
def test_worker_settings_importable():
    from core.queue.worker import WorkerSettings
    assert "run_research_job" in [f.__name__ for f in WorkerSettings.functions]
```

Run: `pytest tests/unit/test_worker_settings.py -v`

---

## Phase 6 — API routes

---

### Task 6.1 — Implement POST /v1/research

**Start state:** Phase 5 complete.

**What to do:**
Create `api/routes/__init__.py` (empty).

Create `api/routes/research.py`:

```python
import uuid
import json
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from db.session import get_db_session
from db.models.research_job import ResearchJob
from arq import create_pool
from core.queue.worker import get_redis_settings

router = APIRouter(prefix="/v1", tags=["research"])

class ResearchRequest(BaseModel):
    query: str
    max_rounds: int = 3
    priority: int = 3
    model_override: Optional[str] = None
    metadata: Optional[dict] = None

class ResearchResponse(BaseModel):
    id: str
    status: str
    query: str
    created_at: str

@router.post("/research", response_model=ResearchResponse, status_code=202)
async def submit_research(body: ResearchRequest, request: Request):
    org_id = request.state.org_id
    api_key_id = request.state.api_key_id

    job_id = f"job_{uuid.uuid4().hex[:12]}"

    async with get_db_session() as db:
        job = ResearchJob(
            id=job_id,
            org_id=org_id,
            api_key_id=api_key_id,
            query=body.query,
            status="queued",
            max_rounds=min(body.max_rounds, 5),
            priority=max(1, min(5, body.priority)),
            model_override=body.model_override,
            metadata_json=json.dumps(body.metadata) if body.metadata else None,
        )
        db.add(job)

    # Store query_text for audit middleware
    request.state.query_text = body.query

    redis = await create_pool(get_redis_settings())
    await redis.enqueue_job("run_research_job", job_id, _job_id=job_id)
    await redis.aclose()

    return ResearchResponse(
        id=job_id,
        status="queued",
        query=body.query,
        created_at=job.created_at.isoformat(),
    )
```

Mount the router in `api/app.py`:

```python
from api.routes.research import router as research_router
app.include_router(research_router)
```

**End state:** `POST /v1/research` returns 202 with job details.

**Test:**

```python
# tests/integration/test_research_submit.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_submit_research_returns_202():
    from api.app import app

    # Patch middleware to inject auth state
    async def mock_auth(request, call_next):
        request.state.org_id = "org_test"
        request.state.api_key_id = "key_test"
        request.state.scope = "research:write"
        return await call_next(request)

    async def mock_audit(request, call_next):
        return await call_next(request)

    with patch("api.middleware.auth.auth_middleware", mock_auth), \
         patch("api.middleware.audit_log.audit_log_middleware", mock_audit), \
         patch("api.routes.research.create_pool") as mock_pool, \
         patch("db.session.get_db_session") as mock_db:

        mock_redis = AsyncMock()
        mock_pool.return_value = mock_redis

        mock_session = AsyncMock()
        mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/research",
                json={"query": "What is the CAR-T therapy market?"},
                headers={"Authorization": "Bearer drapi_live_test_key"},
            )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert "id" in data
    assert data["query"] == "What is the CAR-T therapy market?"
```

Run: `pytest tests/integration/test_research_submit.py -v`

---

### Task 6.2 — Implement GET /v1/research/{id}

**Start state:** Task 6.1 complete.

**What to do:**
Add to `api/routes/research.py`:

```python
from db.models.report import Report
from sqlalchemy import select

@router.get("/research/{job_id}")
async def get_research_job(job_id: str, request: Request):
    org_id = request.state.org_id

    async with get_db_session() as db:
        job = await db.get(ResearchJob, job_id)

    if not job or job.org_id != org_id:
        raise HTTPException(status_code=404, detail="Job not found")

    response_data = {
        "id": job.id,
        "status": job.status,
        "query": job.query,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error": job.error,
    }

    if job.status == "completed":
        async with get_db_session() as db:
            result = await db.execute(
                select(Report).where(Report.job_id == job_id)
            )
            report = result.scalar_one_or_none()

        if report:
            import json
            content_json = json.loads(report.content_json) if report.content_json else {}
            response_data["report"] = {
                "id": report.id,
                "summary": report.summary,
                "body_md": report.content_md,
                "citations": content_json.get("citations", []),
            }

    return response_data
```

**End state:** `GET /v1/research/{id}` returns job status and report when complete.

**Test:**

```python
# tests/unit/test_get_research.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_get_job_returns_queued_status():
    from httpx import AsyncClient, ASGITransport
    from api.app import app
    from db.models.research_job import ResearchJob

    mock_job = ResearchJob(
        id="job_abc123",
        org_id="org_test",
        api_key_id="key_test",
        query="Test query",
        status="queued",
        max_rounds=3,
        priority=3,
        created_at=datetime.now(timezone.utc),
    )

    async def mock_auth(request, call_next):
        request.state.org_id = "org_test"
        request.state.api_key_id = "key_test"
        request.state.scope = "research:read"
        return await call_next(request)

    async def mock_audit(request, call_next):
        return await call_next(request)

    with patch("api.middleware.auth.auth_middleware", mock_auth), \
         patch("api.middleware.audit_log.audit_log_middleware", mock_audit):

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_job

        with patch("db.session.get_db_session") as mock_db_ctx:
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get(
                    "/v1/research/job_abc123",
                    headers={"Authorization": "Bearer drapi_live_test_key"},
                )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "job_abc123"
    assert data["status"] == "queued"
```

Run: `pytest tests/unit/test_get_research.py -v`

---

### Task 6.3 — Implement DELETE /v1/research/{id}

**Start state:** Task 6.2 complete.

**What to do:**
Add to `api/routes/research.py`:

```python
@router.delete("/research/{job_id}", status_code=204)
async def cancel_research_job(job_id: str, request: Request):
    org_id = request.state.org_id

    async with get_db_session() as db:
        job = await db.get(ResearchJob, job_id)

        if not job or job.org_id != org_id:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status in ("completed", "failed", "cancelled"):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot cancel job with status: {job.status}"
            )

        job.status = "cancelled"
        job.finished_at = datetime.now(timezone.utc) if True else None

    from datetime import datetime, timezone
    async with get_db_session() as db:
        job = await db.get(ResearchJob, job_id)
        job.finished_at = datetime.now(timezone.utc)
```

Fix the import at the top of `research.py`:

```python
from datetime import datetime, timezone
```

**End state:** `DELETE /v1/research/{id}` sets status to cancelled.

**Test:**

```python
# tests/unit/test_cancel_research.py
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from db.models.research_job import ResearchJob

@pytest.mark.asyncio
async def test_cancel_completed_job_returns_409():
    from httpx import AsyncClient, ASGITransport
    from api.app import app

    mock_job = ResearchJob(
        id="job_done", org_id="org_test", api_key_id="k",
        query="q", status="completed", max_rounds=3, priority=3,
        created_at=datetime.now(timezone.utc),
    )

    async def mock_auth(request, call_next):
        request.state.org_id = "org_test"
        request.state.api_key_id = "key_test"
        request.state.scope = "research:write"
        return await call_next(request)

    async def mock_audit(request, call_next):
        return await call_next(request)

    with patch("api.middleware.auth.auth_middleware", mock_auth), \
         patch("api.middleware.audit_log.audit_log_middleware", mock_audit):
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_job

        with patch("db.session.get_db_session") as mock_db_ctx:
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.delete(
                    "/v1/research/job_done",
                    headers={"Authorization": "Bearer drapi_live_test_key"},
                )

    assert response.status_code == 409
```

Run: `pytest tests/unit/test_cancel_research.py -v`

---

### Task 6.4 — Implement GET /v1/reports/{id}/export (markdown only)

**Start state:** Task 6.3 complete.

**What to do:**
Create `api/routes/reports.py`:

```python
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy import select
from db.session import get_db_session
from db.models.report import Report
from db.models.research_job import ResearchJob
import json

router = APIRouter(prefix="/v1", tags=["reports"])

@router.get("/reports/{report_id}/export")
async def export_report(report_id: str, format: str = "md", request: Request = None):
    org_id = request.state.org_id

    async with get_db_session() as db:
        report = await db.get(Report, report_id)

    if not report or report.org_id != org_id:
        raise HTTPException(status_code=404, detail="Report not found")

    if format == "md":
        return PlainTextResponse(
            content=report.content_md or "",
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="report-{report_id}.md"'},
        )
    elif format == "json":
        citations = json.loads(report.content_json).get("citations", []) if report.content_json else []
        return JSONResponse({
            "id": report.id,
            "summary": report.summary,
            "body_md": report.content_md,
            "citations": citations,
        })
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Supported: md, json")
```

Mount in `api/app.py`:

```python
from api.routes.reports import router as reports_router
app.include_router(reports_router)
```

**End state:** `GET /v1/reports/{id}/export?format=md` returns markdown content.

**Test:**

```python
# tests/unit/test_report_export.py
import pytest
from unittest.mock import AsyncMock, patch
from db.models.report import Report
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_export_md_returns_markdown():
    from httpx import AsyncClient, ASGITransport
    from api.app import app

    mock_report = Report(
        id="rpt_abc",
        job_id="job_xyz",
        org_id="org_test",
        summary="Summary here",
        content_md="## Report\nContent here",
        content_json='{"citations": []}',
        created_at=datetime.now(timezone.utc),
    )

    async def mock_auth(request, call_next):
        request.state.org_id = "org_test"
        request.state.api_key_id = "key_test"
        request.state.scope = "research:read"
        return await call_next(request)

    async def mock_audit(request, call_next):
        return await call_next(request)

    with patch("api.middleware.auth.auth_middleware", mock_auth), \
         patch("api.middleware.audit_log.audit_log_middleware", mock_audit):
        mock_session = AsyncMock()
        mock_session.get.return_value = mock_report

        with patch("db.session.get_db_session") as mock_db_ctx:
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get(
                    "/v1/reports/rpt_abc/export?format=md",
                    headers={"Authorization": "Bearer drapi_live_test_key"},
                )

    assert response.status_code == 200
    assert "## Report" in response.text
```

Run: `pytest tests/unit/test_report_export.py -v`

---

### Task 6.5 — Implement GET /health/ready

**Start state:** Task 6.4 complete.

**What to do:**
Create `api/routes/health.py`:

```python
from fastapi import APIRouter
from sqlalchemy import text
from db.engine import engine
import redis.asyncio as aioredis
from core.config import settings

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_basic():
    return {"status": "ok"}

@router.get("/health/ready")
async def health_ready():
    checks = {}

    # Check PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {str(e)[:100]}"

    # Check Redis
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)[:100]}"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
```

Mount in `api/app.py` (replace the inline `/health` route):

```python
from api.routes.health import router as health_router
app.include_router(health_router)
```

Remove the inline `@app.get("/health")` definition from `app.py`.

**End state:** `/health/ready` reports postgres and redis status.

**Test:**

```bash
uvicorn api.app:app --port 8000 &
sleep 2
curl -s http://localhost:8000/health/ready | python3 -m json.tool
# Expected: {"status": "ready", "checks": {"postgres": "ok", "redis": "ok"}}
kill %1
```

---

## Phase 7 — Docker and end-to-end validation

---

### Task 7.1 — Write the Dockerfile

**Start state:** Phase 6 complete.

**What to do:**
Create `deploy/Dockerfile`:

```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**End state:** Image builds successfully.

**Test:**

```bash
docker build -f deploy/Dockerfile -t deep-research-api:test .
# Expected: Successfully built <image_id>
docker run --rm deep-research-api:test python -c "import api.app; print('OK')"
```

---

### Task 7.2 — Write Docker Compose

**Start state:** Task 7.1 complete.

**What to do:**
Create `deploy/docker-compose.yml`:

```yaml
version: "3.9"

x-api-env: &api-env
  DATABASE_URL: postgresql+asyncpg://postgres:${PG_PASSWORD:-devpassword}@postgres:5432/drapi
  REDIS_URL: redis://redis:6379/0
  SECRET_KEY: ${SECRET_KEY:-changeme-dev-secret-32chars-min}
  SEARXNG_URL: http://searxng:8080
  ENVIRONMENT: production

services:
  api:
    image: deep-research-api:latest
    build:
      context: ..
      dockerfile: deploy/Dockerfile
    ports:
      - "8000:8000"
    environment:
      <<: *api-env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  worker:
    image: deep-research-api:latest
    command: python -m arq core.queue.worker.WorkerSettings
    environment:
      <<: *api-env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: drapi
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${PG_PASSWORD:-devpassword}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  searxng:
    image: searxng/searxng:latest
    volumes:
      - ./searxng:/etc/searxng:rw
    environment:
      - SEARXNG_BASE_URL=http://localhost:8080/

volumes:
  pgdata:
  redisdata:
```

Create `deploy/searxng/settings.yml` with minimal SearXNG config:

```yaml
use_default_settings: true
server:
  secret_key: "changeme"
  limiter: false
search:
  safe_search: 0
  formats:
    - html
    - json
```

**End state:** `docker compose up` starts all services.

**Test:**

```bash
cd deploy
docker compose up -d
sleep 10
curl -s http://localhost:8000/health/ready
# Expected: {"status":"ready","checks":{"postgres":"ok","redis":"ok"}}
docker compose down
```

---

### Task 7.3 — Write the database migration entrypoint script

**Start state:** Task 7.2 complete.

**What to do:**
Create `scripts/migrate.py`:

```python
"""Run Alembic migrations to head. Called before starting the API in production."""
import subprocess
import sys

if __name__ == "__main__":
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print("Migrations complete.")
```

Update `deploy/Dockerfile` CMD to run migrations first:

```dockerfile
CMD ["sh", "-c", "python scripts/migrate.py && uvicorn api.app:app --host 0.0.0.0 --port 8000"]
```

**End state:** Starting the API container automatically applies all migrations.

**Test:**

```bash
cd deploy
docker compose up -d postgres
sleep 5
docker compose run --rm api python scripts/migrate.py
# Expected: "Migrations complete."
docker compose down
```

---

### Task 7.4 — Write the seed script (create first org and API key)

**Start state:** Task 7.3 complete.

**What to do:**
Create `scripts/seed.py`:

```python
"""
Create a seed organisation and API key for local development and first-run setup.
Usage: python scripts/seed.py --org-name "Acme Pharma" --backend-provider openai \
         --backend-url https://api.openai.com/v1 --backend-key sk-... --backend-model gpt-4o
"""
import asyncio
import uuid
import argparse
from db.session import get_db_session
from db.models.org import Org
from db.models.api_key import APIKey
from db.models.llm_backend import LLMBackend
from core.security.api_keys import generate_api_key
from core.security.encryption import encrypt

async def seed(org_name: str, provider: str, base_url: str, api_key_val: str, model: str):
    org_id = f"org_{uuid.uuid4().hex[:12]}"
    full_key, key_hash = generate_api_key(org_id)

    async with get_db_session() as db:
        org = Org(id=org_id, name=org_name)
        db.add(org)

        api_key = APIKey(
            id=f"key_{uuid.uuid4().hex[:12]}",
            org_id=org_id,
            name="Default key",
            key_hash=key_hash,
            scope="research:write,research:read",
        )
        db.add(api_key)

        backend = LLMBackend(
            id=f"be_{uuid.uuid4().hex[:12]}",
            org_id=org_id,
            name=f"{provider}-default",
            provider=provider,
            base_url=base_url,
            api_key_encrypted=encrypt(api_key_val) if api_key_val else None,
            model=model,
            is_default=True,
        )
        db.add(backend)

    print(f"Org ID:  {org_id}")
    print(f"API Key: {full_key}")
    print("(Save this key — it will not be shown again.)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-name", required=True)
    parser.add_argument("--backend-provider", default="openai")
    parser.add_argument("--backend-url", default="https://api.openai.com/v1")
    parser.add_argument("--backend-key", default="")
    parser.add_argument("--backend-model", default="gpt-4o")
    args = parser.parse_args()
    asyncio.run(seed(args.org_name, args.backend_provider, args.backend_url, args.backend_key, args.backend_model))
```

**End state:** Running the seed script creates an org with a usable API key.

**Test:**

```bash
python scripts/seed.py \
  --org-name "Test Org" \
  --backend-provider openai \
  --backend-url https://api.openai.com/v1 \
  --backend-key sk-test \
  --backend-model gpt-4o
# Expected output: Org ID: org_... / API Key: drapi_live_...
```

---

### Task 7.5 — End-to-end smoke test (live stack)

**Start state:** Task 7.4 complete. A real LLM endpoint and SearXNG instance are available.

**What to do:**
Create `tests/e2e/test_smoke.py`:

```python
"""
Smoke test against a live running stack.
Set E2E_API_KEY and E2E_BASE_URL environment variables before running.
"""
import os
import asyncio
import httpx
import pytest
import time

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("E2E_API_KEY", "")

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_health_ready():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_submit_and_poll_job():
    headers = {"Authorization": f"Bearer {API_KEY}"}
    query = "What are the main competitive players in the CAR-T cell therapy market?"

    async with httpx.AsyncClient() as client:
        # Submit
        r = await client.post(
            f"{BASE_URL}/v1/research",
            json={"query": query, "max_rounds": 1},
            headers=headers,
        )
    assert r.status_code == 202
    job_id = r.json()["id"]

    # Poll until complete or timeout (5 minutes)
    deadline = time.time() + 300
    final_status = None
    async with httpx.AsyncClient() as client:
        while time.time() < deadline:
            r = await client.get(f"{BASE_URL}/v1/research/{job_id}", headers=headers)
            assert r.status_code == 200
            status = r.json()["status"]
            if status in ("completed", "failed", "cancelled"):
                final_status = status
                break
            await asyncio.sleep(5)

    assert final_status == "completed", f"Job ended with status: {final_status}"
    data = r.json()
    assert "report" in data
    assert len(data["report"]["body_md"]) > 100
```

**End state:** A real research job runs end-to-end and returns a report.

**Test:**

```bash
# Start the stack
cd deploy && docker compose up -d

# Seed an org
python scripts/seed.py --org-name "E2E Test" --backend-key YOUR_OPENAI_KEY

# Run the smoke test
E2E_BASE_URL=http://localhost:8000 \
E2E_API_KEY=drapi_live_... \
pytest tests/e2e/test_smoke.py -v -m e2e
```

---

## Summary

| Phase | Tasks     | Deliverable                                                                    |
| ----- | --------- | ------------------------------------------------------------------------------ |
| 0     | 0.1 – 0.9 | Repo scaffold, all DB models, Alembic migrations live                          |
| 1     | 1.1 – 1.5 | Encryption, API key auth, audit middleware, FastAPI app starts                 |
| 2     | 2.1 – 2.4 | LLM client abstracts OpenAI and Anthropic, routes correctly                    |
| 3     | 3.1 – 3.2 | SearXNG search client, URL fetcher with HTML stripping                         |
| 4     | 4.1 – 4.4 | Planner, extractor, synthesizer, full IterResearch engine                      |
| 5     | 5.1 – 5.2 | ARQ job queue wired, worker settings defined                                   |
| 6     | 6.1 – 6.5 | All API routes live: submit, poll, cancel, export, health                      |
| 7     | 7.1 – 7.5 | Dockerfile, Docker Compose, migrations on startup, seed script, e2e smoke test |

**Total: 36 tasks.** Each one is independently testable. Pass them sequentially to your LLM.
