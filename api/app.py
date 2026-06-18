import os
import uuid

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware order: audit runs outermost (wraps auth), auth runs before routes
app.add_middleware(BaseHTTPMiddleware, dispatch=audit_log_middleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

app.include_router(health_router)
app.include_router(research_router)
app.include_router(reports_router)
app.include_router(sources_router)
app.include_router(webhooks_router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/", response_class=HTMLResponse)
async def read_index():
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(static_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
