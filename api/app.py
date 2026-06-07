from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from db.engine import engine
from api.middleware.auth import auth_middleware
from api.middleware.audit_log import audit_log_middleware
from api.routes.health import router as health_router
from api.routes.research import router as research_router
from api.routes.reports import router as reports_router
from api.routes.sources import router as sources_router
from api.routes.webhooks import router as webhooks_router
from fastapi.responses import HTMLResponse
import os



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

app.include_router(health_router)
app.include_router(research_router)
app.include_router(reports_router)
app.include_router(sources_router)
app.include_router(webhooks_router)


@app.get("/", response_class=HTMLResponse)
async def read_index():
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(static_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


