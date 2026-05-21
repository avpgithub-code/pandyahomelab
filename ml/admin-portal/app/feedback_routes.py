"""Public feedback API — POST /feedback/likes, POST /feedback/comments, GET /feedback/likes.

Anonymous; rate-limited at the DB layer by `ip_hash`:
  - likes:    1 per IP per page per day  (silent dedup, current count still returned)
  - comments: 1 per IP per hour          (429 returned on excess)
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator

from app.feedback_queries import (
    can_comment,
    count_likes,
    insert_comment,
    insert_like,
)
from app.ip_hasher import hash_request_ip

logger = logging.getLogger("admin-portal.feedback")
router = APIRouter(prefix="/feedback", tags=["feedback"])


# ───────────────────────── Pydantic models ─────────────────────────

class LikeRequest(BaseModel):
    page_id: str = Field(..., min_length=1, max_length=255)

    @field_validator("page_id")
    @classmethod
    def _start_with_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError("page_id must start with /")
        return v


class CommentRequest(BaseModel):
    page_id: str = Field(..., min_length=1, max_length=255)
    name:    Optional[str] = Field(None, max_length=80)
    body:    str = Field(..., min_length=3, max_length=2000)

    @field_validator("page_id")
    @classmethod
    def _page_id_starts_with_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError("page_id must start with /")
        return v

    @field_validator("name", mode="before")
    @classmethod
    def _normalize_name(cls, v):
        if v is None:
            return None
        v = str(v).strip()
        return v or None  # empty string after strip → None

    @field_validator("body", mode="before")
    @classmethod
    def _strip_body(cls, v):
        return str(v or "").strip()


# ─────────────────────────── Endpoints ─────────────────────────────

@router.post("/likes")
async def post_like(payload: LikeRequest, request: Request):
    """Record a like. Always returns the current total; `new_like` tells the
    client whether their click counted (false = already liked within the day)."""
    ip_hash = hash_request_ip(request)
    inserted = insert_like(payload.page_id, ip_hash)
    total = count_likes(payload.page_id)
    if inserted:
        logger.info(f"like recorded · page={payload.page_id} · ip={ip_hash[:8]}…")
    return {"ok": True, "new_like": inserted, "total_likes": total}


@router.post("/comments")
async def post_comment(payload: CommentRequest, request: Request):
    """Record a comment. 429 if this IP has commented within the last hour."""
    ip_hash = hash_request_ip(request)
    if not can_comment(ip_hash):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="One comment per hour, please. Try again later.",
        )
    cid = insert_comment(payload.page_id, ip_hash, payload.name, payload.body)
    logger.info(
        f"comment recorded · id={cid} · page={payload.page_id} "
        f"· ip={ip_hash[:8]}… · chars={len(payload.body)}"
    )
    return {"ok": True, "message": "Thanks — your feedback was received."}


@router.get("/likes")
async def get_likes(page_id: str = Query(..., min_length=1, max_length=255)):
    """Read-only — returns the current like count for the page."""
    if not page_id.startswith("/"):
        page_id = "/" + page_id
    return {"page_id": page_id, "total_likes": count_likes(page_id)}
