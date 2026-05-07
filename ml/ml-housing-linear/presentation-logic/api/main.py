from datetime import datetime
from fastapi import FastAPI

from presentation_logic.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Housing Linear Regression",
        description="Linear Regression model for California housing price prediction",
        version="1.0.0-alpha1",
    )

    app.include_router(router)

    @app.on_event("startup")
    async def startup_event():
        print(f"[{datetime.utcnow().isoformat()}] Housing Linear service starting")

    @app.on_event("shutdown")
    async def shutdown_event():
        print(f"[{datetime.utcnow().isoformat()}] Housing Linear service shutting down")

    return app


app = create_app()
