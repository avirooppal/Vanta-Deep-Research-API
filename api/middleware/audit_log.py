import time
from fastapi import Request
from db.session import get_db_session
from db.models.audit_log import AuditLog


async def audit_log_middleware(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)

    org_id = getattr(request.state, "org_id", None)
    api_key_id = getattr(request.state, "api_key_id", None)

    # Extract query text for research submissions only (set by route handler)
    query_text = None
    if request.url.path == "/v1/research" and request.method == "POST":
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
