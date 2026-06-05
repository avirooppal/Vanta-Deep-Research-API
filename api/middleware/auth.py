from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from db.session import get_db_session
from db.models.api_key import APIKey
from db.models.org import Org
from core.security.api_keys import verify_api_key

# Paths that skip authentication
_PUBLIC_PATHS = {"/health", "/health/ready", "/health/live", "/docs", "/openapi.json"}


async def auth_middleware(request: Request, call_next):
    if request.url.path in _PUBLIC_PATHS:
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
