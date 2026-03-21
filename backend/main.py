"""
backend/main.py
FastAPI application factory — startup, middleware, router registration.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi import HTTPException
from loguru import logger

from backend.core.config import settings
from backend.core.database import check_db_connection, engine, Base
from backend.api.middleware.rate_limit import RateLimitMiddleware
from backend.api.middleware.error_handler import (
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)


# ── Lifespan ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup and shutdown tasks."""
    logger.info(f"Starting {settings.app_name} [{settings.app_env}]")

    # Create all tables if they don't exist (safe — won't drop existing data)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured")

    # Verify DB connection
    if not check_db_connection():
        logger.warning("Could not connect to database — check Docker is running")

    # Start scheduler (Phase 10)
    try:
        from backend.services.scheduler_service import SchedulerService
        app.state.scheduler = SchedulerService()
        app.state.scheduler.start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")

    logger.info(f"Server ready on port {settings.app_port}")
    yield

    # Shutdown
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.stop()
    logger.info("Shutting down...")


# ── App Factory ───────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="AI-powered chatbot for VTU exam schedules and circulars",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Exception handlers ────────────────────────────────────
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # ── Middleware ────────────────────────────────────────────
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ───────────────────────────────────────────────
    from backend.api.routes.chat import router as chat_router
    from backend.api.routes.circulars import router as circulars_router
    from backend.api.routes.schedule import router as schedule_router
    from backend.api.routes.notifications import router as notifications_router

    app.include_router(chat_router,          prefix="/api/v1", tags=["Chat"])
    app.include_router(circulars_router,     prefix="/api/v1", tags=["Circulars"])
    app.include_router(schedule_router,      prefix="/api/v1", tags=["Exam Schedule"])
    app.include_router(notifications_router, prefix="/api/v1", tags=["Notifications"])

    # Admin routes (Phase 10)
    try:
        from backend.api.routes.admin import router as admin_router
        app.include_router(admin_router, prefix="/api/v1", tags=["Admin"])
    except ImportError:
        pass

    # ── Health check ─────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    def health():
        db_ok = check_db_connection()
        return {
            "status": "ok" if db_ok else "degraded",
            "app": settings.app_name,
            "env": settings.app_env,
            "database": "ok" if db_ok else "unavailable",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.is_development,
    )
