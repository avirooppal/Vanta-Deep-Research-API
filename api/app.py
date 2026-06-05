from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from db.engine import engine
from api.middleware.auth import auth_middleware
from api.middleware.audit_log import audit_log_middleware


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

# Middleware order: audit runs outermost (wraps auth), auth runs before routes
app.add_middleware(BaseHTTPMiddleware, dispatch=audit_log_middleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    return {"status": "ok"}


@app.get("/health/live")
async def health_live():
    return {"status": "ok"}
