"""HTTP error response handlers."""
from fastapi import Request
from fastapi.responses import JSONResponse


class MLServiceError(Exception):
    """Custom ML service error."""
    pass


async def ml_service_error_handler(request: Request, exc: MLServiceError):
    """Handle ML service errors."""
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": "MLServiceError"},
    )
