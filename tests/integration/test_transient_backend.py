import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from contextlib import ExitStack
from httpx import AsyncClient, ASGITransport

def _make_api_key(org_id="org_test"):
    key = MagicMock()
    key.org_id = org_id
    key.id = "key_test"
    key.scope = "research:write,research:read"
    key.key_hash = "anyhash"
    key.is_active = True
    return key

def _make_org(org_id="org_test"):
    org = MagicMock()
    org.is_active = True
    org.id = org_id
    return org

def _ctx(session):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx

@pytest.mark.asyncio
async def test_submit_research_with_transient_key():
    from api.app import app
    from db.models.org import Org
    from db.models.api_key import APIKey
    from core.security.encryption import decrypt

    auth_session = AsyncMock()
    auth_session.add = MagicMock()
    
    # Empty active keys list so verify_api_key loop isn't matched
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    auth_session.execute = AsyncMock(return_value=result)
    
    transient_org = Org(id="org_transient", name="Transient Org", is_active=True)
    transient_key = APIKey(id="key_transient", org_id="org_transient", is_active=True, scope="research:write,research:read")
    
    def mock_get(model, pk):
        if model.__name__ == "Org" and pk == "org_transient":
            return transient_org
        if model.__name__ == "APIKey" and pk == "key_transient":
            return transient_key
        return None
        
    auth_session.get.side_effect = mock_get

    route_session = AsyncMock()
    route_session.add = MagicMock()
    
    added_jobs = []
    def mock_add(obj):
        if obj.__class__.__name__ == "ResearchJob":
            added_jobs.append(obj)
            
    route_session.add.side_effect = mock_add

    mock_redis = AsyncMock()

    with ExitStack() as stack:
        stack.enter_context(patch("api.middleware.auth.get_db_session", side_effect=lambda: _ctx(auth_session)))
        stack.enter_context(patch("api.middleware.audit_log.get_db_session", side_effect=lambda: _ctx(auth_session)))
        stack.enter_context(patch("api.routes.research.get_db_session", side_effect=lambda: _ctx(route_session)))
        stack.enter_context(patch("api.routes.research.create_pool", return_value=mock_redis))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/research",
                json={"query": "What is the capital of France?"},
                headers={"Authorization": "Bearer sk-ant-mycustomtoken"},
            )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert len(added_jobs) == 1
    job = added_jobs[0]
    assert job.org_id == "org_transient"
    assert job.api_key_id == "key_transient"
    
    meta = json.loads(job.metadata_json)
    assert "transient_backend" in meta
    tb = meta["transient_backend"]
    assert tb["provider"] == "anthropic"
    assert tb["model"] == "claude-3-5-sonnet-latest"
    assert tb["base_url"] == "https://api.anthropic.com/v1"
    assert "api_key_encrypted" in tb
    assert decrypt(tb["api_key_encrypted"]) == "sk-ant-mycustomtoken"


@pytest.mark.asyncio
async def test_submit_research_with_body_overrides():
    from api.app import app
    from core.security.encryption import decrypt

    auth_session = AsyncMock()
    auth_session.add = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [_make_api_key()]
    auth_session.execute = AsyncMock(return_value=result)
    auth_session.get.side_effect = lambda model, pk: _make_org() if model.__name__ == "Org" else None

    route_session = AsyncMock()
    route_session.add = MagicMock()
    
    added_jobs = []
    def mock_add(obj):
        if obj.__class__.__name__ == "ResearchJob":
            added_jobs.append(obj)
            
    route_session.add.side_effect = mock_add

    mock_redis = AsyncMock()

    with ExitStack() as stack:
        stack.enter_context(patch("api.middleware.auth.get_db_session", side_effect=lambda: _ctx(auth_session)))
        stack.enter_context(patch("api.middleware.audit_log.get_db_session", side_effect=lambda: _ctx(auth_session)))
        stack.enter_context(patch("api.middleware.auth.verify_api_key", return_value=True))
        stack.enter_context(patch("api.routes.research.get_db_session", side_effect=lambda: _ctx(route_session)))
        stack.enter_context(patch("api.routes.research.create_pool", return_value=mock_redis))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/research",
                json={
                    "query": "Testing body overrides",
                    "provider": "openai",
                    "api_key": "sk-my-custom-openai-key",
                    "base_url": "https://custom.openai.api",
                    "model": "gpt-custom-model"
                },
                headers={"Authorization": "Bearer drapi_live_test_key"},
            )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert len(added_jobs) == 1
    job = added_jobs[0]
    assert job.org_id == "org_test"
    assert job.api_key_id == "key_test"
    
    meta = json.loads(job.metadata_json)
    assert "transient_backend" in meta
    tb = meta["transient_backend"]
    assert tb["provider"] == "openai"
    assert tb["model"] == "gpt-custom-model"
    assert tb["base_url"] == "https://custom.openai.api"
    assert decrypt(tb["api_key_encrypted"]) == "sk-my-custom-openai-key"


@pytest.mark.asyncio
async def test_worker_task_handles_transient_backend():
    from core.queue.tasks import run_research_job
    from db.models.research_job import ResearchJob
    from core.security.encryption import encrypt

    # Prepare job with transient backend config
    transient_backend = {
        "provider": "openai",
        "api_key_encrypted": encrypt("sk-my-custom-openai-key").decode("utf-8"),
        "base_url": "https://custom.openai.api",
        "model": "gpt-custom-model"
    }
    
    mock_job = ResearchJob(
        id="job_transient_test",
        org_id="org_transient",
        api_key_id="key_transient",
        query="What is the meaning of life?",
        status="queued",
        max_rounds=1,
        priority=3,
        metadata_json=json.dumps({"transient_backend": transient_backend}),
        created_at=datetime.now(timezone.utc)
    )

    db_session = AsyncMock()
    db_session.get = AsyncMock(return_value=mock_job)

    mock_llm_client_instance = MagicMock()
    mock_llm_client_instance.total_tokens_in = 0
    mock_llm_client_instance.total_tokens_out = 0
    mock_llm_client_instance.search_queries_issued = 0
    mock_llm_client_instance.sources_fetched = 0

    mock_report = MagicMock()
    mock_report.query = "What is the meaning of life?"
    mock_report.summary = "Summary"
    mock_report.body_md = "Body"
    mock_report.citations = []

    with ExitStack() as stack:
        stack.enter_context(patch("core.queue.tasks.get_db_session", side_effect=lambda: _ctx(db_session)))
        mock_llm_client_class = stack.enter_context(patch("core.queue.tasks.LLMClient", return_value=mock_llm_client_instance))
        stack.enter_context(patch("core.queue.tasks.run_research", AsyncMock(return_value=mock_report)))

        await run_research_job({}, "job_transient_test")

    # Verify LLMClient was initialized with the decrypted transient config
    mock_llm_client_class.assert_called_once()
    config_passed = mock_llm_client_class.call_args[0][0]
    assert config_passed.provider == "openai"
    assert config_passed.base_url == "https://custom.openai.api"
    assert config_passed.api_key == "sk-my-custom-openai-key"
    assert config_passed.model == "gpt-custom-model"


@pytest.mark.asyncio
async def test_submit_research_with_openrouter_key():
    from api.app import app
    from db.models.org import Org
    from db.models.api_key import APIKey
    from core.security.encryption import decrypt

    auth_session = AsyncMock()
    auth_session.add = MagicMock()
    
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    auth_session.execute = AsyncMock(return_value=result)
    
    transient_org = Org(id="org_transient", name="Transient Org", is_active=True)
    transient_key = APIKey(id="key_transient", org_id="org_transient", is_active=True, scope="research:write,research:read")
    
    def mock_get(model, pk):
        if model.__name__ == "Org" and pk == "org_transient":
            return transient_org
        if model.__name__ == "APIKey" and pk == "key_transient":
            return transient_key
        return None
        
    auth_session.get.side_effect = mock_get

    route_session = AsyncMock()
    route_session.add = MagicMock()
    
    added_jobs = []
    def mock_add(obj):
        if obj.__class__.__name__ == "ResearchJob":
            added_jobs.append(obj)
            
    route_session.add.side_effect = mock_add

    mock_redis = AsyncMock()

    with ExitStack() as stack:
        stack.enter_context(patch("api.middleware.auth.get_db_session", side_effect=lambda: _ctx(auth_session)))
        stack.enter_context(patch("api.middleware.audit_log.get_db_session", side_effect=lambda: _ctx(auth_session)))
        stack.enter_context(patch("api.routes.research.get_db_session", side_effect=lambda: _ctx(route_session)))
        stack.enter_context(patch("api.routes.research.create_pool", return_value=mock_redis))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/v1/research",
                json={"query": "OpenRouter test query"},
                headers={"Authorization": "Bearer sk-or-v1-myopenroutertoken"},
            )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert len(added_jobs) == 1
    job = added_jobs[0]
    assert job.org_id == "org_transient"
    assert job.api_key_id == "key_transient"
    
    meta = json.loads(job.metadata_json)
    assert "transient_backend" in meta
    tb = meta["transient_backend"]
    assert tb["provider"] == "openrouter"
    assert tb["model"] == "google/gemini-2.5-flash:free"
    assert tb["base_url"] == "https://openrouter.ai/api/v1"
    assert "api_key_encrypted" in tb
    assert decrypt(tb["api_key_encrypted"]) == "sk-or-v1-myopenroutertoken"
