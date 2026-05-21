"""HTTP Basic Auth for the admin portal.

Credentials come from ADMIN_USERNAME and ADMIN_PASSWORD env vars.
Uses secrets.compare_digest for constant-time comparison (prevents timing attacks).
"""
import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()


def get_current_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    username = os.environ.get("ADMIN_USERNAME") or ""
    password = os.environ.get("ADMIN_PASSWORD") or ""

    if not username or not password:
        # Service mis-configured. Fail closed.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin auth not configured",
        )

    correct_user = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        username.encode("utf-8"),
    )
    correct_pass = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        password.encode("utf-8"),
    )

    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
