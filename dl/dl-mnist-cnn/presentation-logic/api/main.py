"""FastAPI application factory for dl-mnist-cnn."""
from datetime import datetime

from fastapi import FastAPI

from presentation_logic.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="dl-mnist-cnn",
        description="Handwritten digit classification (PyTorch CNN, MNIST) with HTML5 canvas UI",
        version="1.0.0-alpha1",
    )
    app.include_router(router)

    @app.on_event("startup")
    async def startup_event():
        print(f"[{datetime.utcnow().isoformat()}] dl-mnist-cnn service starting")

    @app.on_event("shutdown")
    async def shutdown_event():
        print(f"[{datetime.utcnow().isoformat()}] dl-mnist-cnn service shutting down")

    return app


app = create_app()
