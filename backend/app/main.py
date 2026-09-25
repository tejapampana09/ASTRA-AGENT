from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.approvals import router as approvals_router
from app.api.routes.benchmarks import router as benchmarks_router
from app.api.routes.events import router as events_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.repositories import router as repositories_router
from app.api.routes.tasks import router as tasks_router
from app.config import settings
from app.observability.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} in {settings.ENVIRONMENT} mode")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title="ASTRA 2.0 API",
    description="Autonomous Software Engineering Agent Platform",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(tasks_router, prefix="/api")
app.include_router(repositories_router, prefix="/api")
app.include_router(approvals_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(benchmarks_router, prefix="/api")


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
    }
