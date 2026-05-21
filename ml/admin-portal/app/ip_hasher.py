"""Extract the visitor IP from request headers and hash it with the shared salt.

The hash format matches `analytics-ingester/ingester/enricher.py` exactly:
    SHA-256(f"{salt}:{ip}")
…so rate-limiting checks against `analytics.visitor_events.ip_hash` find matches.
"""
import hashlib
import os
from typing import Optional

from fastapi import Request


def hash_ip(ip: str, salt: Optional[str] = None) -> str:
    """Salted SHA-256 hex digest. Unknown IP returns 64 zeros (matches ingester)."""
    if salt is None:
        salt = os.environ.get("ANALYTICS_IP_SALT", "")
    if not ip:
        return "0" * 64
    return hashlib.sha256(f"{salt}:{ip}".encode("utf-8")).hexdigest()


def get_real_ip(request: Request) -> str:
    """Extract the real visitor IP, preferring Cloudflare's header.

    Order of preference:
      1. CF-Connecting-IP — set by Cloudflare Tunnel
      2. X-Forwarded-For — first hop (in case CF is bypassed)
      3. request.client.host — direct connection (local curl tests)
    """
    cf = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf:
        return cf
    xff = request.headers.get("x-forwarded-for") or ""
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


def hash_request_ip(request: Request) -> str:
    return hash_ip(get_real_ip(request))
