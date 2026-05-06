"""FastAPI application factory for Iris KNN classifier."""
from datetime import datetime
from fastapi import FastAPI

from presentation_logic.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Iris KNN Classifier",
        description="K-Nearest Neighbors classifier for Iris species prediction",
        version="1.0.0-alpha1",
    )

    app.include_router(router)

    @app.on_event("startup")
    async def startup_event():
        print(f"[{datetime.utcnow().isoformat()}] Iris KNN service starting")

    @app.on_event("shutdown")
    async def shutdown_event():
        print(f"[{datetime.utcnow().isoformat()}] Iris KNN service shutting down")

    return app


app = create_app()
