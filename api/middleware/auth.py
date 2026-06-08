from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from db.session import get_db_session
from db.models.api_key import APIKey
from db.models.org import Org
from core.security.api_keys import verify_api_key

# Paths that skip authentication
_PUBLIC_PATHS = {"/", "/health", "/health/ready", "/health/live", "/docs", "/openapi.json"}



async def auth_middleware(request: Request, call_next):
    path = request.url.path.rstrip("/")
    if path == "" or path in _PUBLIC_PATHS or request.method == "OPTIONS":
        return await call_next(request)


    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"error": "Missing or invalid Authorization header"},
        )

    presented_key = auth_header.removeprefix("Bearer ").strip()

    async with get_db_session() as db:
        result = await db.execute(select(APIKey).where(APIKey.is_active == True))
        keys = result.scalars().all()

    matched_key = None
    for key in keys:
        if verify_api_key(presented_key, key.key_hash):
            matched_key = key
            break

    if matched_key:
        async with get_db_session() as db:
            org = await db.get(Org, matched_key.org_id)

        if not org or not org.is_active:
            return JSONResponse(status_code=403, content={"error": "Organisation inactive"})

        request.state.org_id = matched_key.org_id
        request.state.api_key_id = matched_key.id
        request.state.scope = matched_key.scope
        request.state.transient_backend = None
    else:
        provider = None
        base_url = None
        default_model = None

        if presented_key.startswith("sk-ant-"):
            provider = "anthropic"
            base_url = "https://api.anthropic.com/v1"
            default_model = "claude-3-5-sonnet-latest"
        elif presented_key.startswith("sk-or-"):
            provider = "openrouter"
            base_url = "https://openrouter.ai/api/v1"
            default_model = "openrouter/free"
        elif presented_key.startswith("sk-"):
            provider = "openai"
            base_url = "https://api.openai.com/v1"
            default_model = "gpt-4o"
        elif presented_key.startswith("AIza"):
            provider = "openai_compatible"
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            default_model = "gemini-2.5-flash"

        provider_header = request.headers.get("X-Provider")
        base_url_header = request.headers.get("X-Base-Url")
        model_header = request.headers.get("X-Model")

        if provider_header:
            provider = provider_header
        if base_url_header:
            base_url = base_url_header
        if model_header:
            default_model = model_header

        if not provider:
            return JSONResponse(status_code=401, content={"error": "Invalid API key"})

        async with get_db_session() as db:
            org = await db.get(Org, "org_transient")
            if not org:
                org = Org(id="org_transient", name="Transient Org", is_active=True)
                db.add(org)
                await db.flush()

            key = await db.get(APIKey, "key_transient")
            if not key:
                key = APIKey(
                    id="key_transient",
                    org_id="org_transient",
                    name="Transient Key",
                    key_hash="transient_hash",
                    scope="research:write,research:read",
                    is_active=True
                )
                db.add(key)
                await db.flush()

        request.state.org_id = "org_transient"
        request.state.api_key_id = "key_transient"
        request.state.scope = "research:write,research:read"
        request.state.transient_backend = {
            "provider": provider,
            "api_key": presented_key,
            "base_url": base_url,
            "model": default_model,
        }

    return await call_next(request)

