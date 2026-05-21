"""FastAPI application factory for the admin portal."""
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="pandyaHomeLab — Admin Portal",
        description="Visitor analytics dashboard (admin only)",
        version="1.0.0-alpha1",
    )
    from app.routes import router
    app.include_router(router)
    return app


app = create_app()
