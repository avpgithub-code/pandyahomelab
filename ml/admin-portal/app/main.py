"""FastAPI application factory for the admin portal.

Routing map:
    /health              → app-root liveness (Docker healthcheck)
    /admin/              → dashboard (Basic Auth)
    /admin/feedback      → moderation view (Basic Auth)
    /admin/feedback/{id}/hide → toggle hidden flag (Basic Auth, POST)
    /feedback/likes      → public like API (anonymous)
    /feedback/comments   → public comment API (anonymous)
    /feedback/likes?page_id=...  → public like count

Nginx (no longer strips the URL prefix) maps:
    pandyahomelab.com/admin/...    → container :8000/admin/...
    pandyahomelab.com/feedback/... → container :8000/feedback/...
"""
import logging
import os

from fastapi import FastAPI

from app.schema import ensure_feedback_schema

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("admin-portal")


def create_app() -> FastAPI:
    app = FastAPI(
        title="pandyaHomeLab — Admin Portal",
        description="Visitor analytics dashboard + public feedback API",
        version="1.0.4",
    )

    @app.on_event("startup")
    async def bootstrap_schema() -> None:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            logger.warning("DATABASE_URL not set — skipping feedback schema bootstrap")
            return
        try:
            ensure_feedback_schema(dsn)
            logger.info("feedback schema bootstrapped (feedback_likes, feedback_comments)")
        except Exception as e:
            logger.warning(f"feedback schema bootstrap failed (will retry on next startup): {e}")

    # Liveness probe at app root — used by the Dockerfile HEALTHCHECK.
    # No auth, no analytics logging.
    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    # Admin views (Basic Auth required) — externally /admin/...
    from app.routes import router as admin_router
    app.include_router(admin_router, prefix="/admin", tags=["admin"])

    # Public feedback API — externally /feedback/... (already has prefix="/feedback")
    from app.feedback_routes import router as feedback_router
    app.include_router(feedback_router)

    return app


app = create_app()
