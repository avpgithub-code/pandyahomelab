"""FastAPI application factory for ml-titanic-automl."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="ML Titanic AutoML",
        description="PyCaret AutoML classifier on Titanic survival dataset",
        version="1.0.0-alpha1",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routes import router
    app.include_router(router)

    return app
