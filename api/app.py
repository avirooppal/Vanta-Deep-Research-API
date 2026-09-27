import os
import uuid

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging import request_id_var
from db.engine import engine
from api.middleware.auth import auth_middleware
from api.middleware.audit_log import audit_log_middleware
from api.routes.health import router as health_router
from api.routes.research import router as research_router
from api.routes.reports import router as reports_router
from api.routes.sources import router as sources_router
from api.routes.webhooks import router as webhooks_router
from core.llm.http import close_http_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_http_client()
    await engine.dispose()
async def request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_var.set(req_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    request_id_var.reset(token)
    return response

app = FastAPI(
    title="Vanta",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(BaseHTTPMiddleware, dispatch=request_id_middleware)

async def private_network_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.headers.get("access-control-request-private-network"):
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

app.add_middleware(BaseHTTPMiddleware, dispatch=private_network_middleware)

# Inner middlewares: audit wraps auth, auth runs before routes
app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=audit_log_middleware)

# Outermost middleware: CORSMiddleware must wrap all responses including 401/422/500
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(health_router)
app.include_router(research_router)
app.include_router(reports_router)
app.include_router(sources_router)
app.include_router(webhooks_router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    error_msg = detail if isinstance(detail, str) else detail.get("error", str(detail))
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error_msg},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import logging
    logging.exception(f"Unhandled server error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": f"Database or internal server error: {str(exc)}"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/console", response_class=HTMLResponse)
async def read_index():
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(static_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
