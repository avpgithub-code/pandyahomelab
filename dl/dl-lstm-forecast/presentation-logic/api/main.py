"""FastAPI application factory and routes initialization."""
from fastapi import FastAPI
from datetime import datetime


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="ML Project",
        description="Machine Learning project service",
        version="1.0.0",
    )

    # Import and include routers
    from .routes import router
    app.include_router(router)

    @app.on_event("startup")
    async def startup_event():
        """Initialize resources on startup."""
        print(f"[{datetime.utcnow().isoformat()}] Application starting")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Clean up resources on shutdown."""
        print(f"[{datetime.utcnow().isoformat()}] Application shutting down")

    return app
