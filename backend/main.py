"""
backend/main.py
FastAPI application factory — startup, middleware, router registration.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.core.config import settings
from backend.core.database import check_db_connection, engine, Base


# ── Lifespan ─────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup and shutdown tasks."""
    logger.info(f"Starting {settings.app_name} [{settings.app_env}]")

    # Create all tables (dev only — use Alembic migrations in prod)
    if settings.is_development:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created")

    # Verify DB connection
    if not check_db_connection():
        logger.warning("Could not connect to database — check Docker is running")

    logger.info(f"Server ready on port {settings.app_port}")
    yield

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

    # ── CORS ─────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173"],
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

    # ── Health check ─────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    def health():
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
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
