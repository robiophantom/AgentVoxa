"""AgentVoxa – FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import create_tables
from core.qdrant import ensure_collection
from routers import (
    auth_router,
    documents_router,
    chat_router,
    calls_router,
    admin_router,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await create_tables()
    await ensure_collection()
    yield
    # Shutdown (nothing to clean up for now)


app = FastAPI(
    title="AgentVoxa API",
    description="AI Receptionist Platform – REST & WebSocket API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
API_PREFIX = "/api"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(documents_router, prefix=API_PREFIX)
app.include_router(chat_router, prefix=API_PREFIX)
app.include_router(calls_router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)


@app.get("/", tags=["health"])
async def root():
    return {"service": "AgentVoxa", "status": "running"}


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
