"""Hash the visitor IP (salted SHA-256) and detect bots from the user agent."""
import hashlib
from typing import Dict, Any

# Case-insensitive substring patterns. Refined as we learn what real bot traffic looks like.
BOT_PATTERNS = (
    # Generic
    "bot", "crawler", "spider", "scraper",
    # Search engines
    "googlebot", "bingbot", "duckduckbot", "slurp", "yandex", "baiduspider",
    # SEO crawlers
    "ahrefsbot", "semrushbot", "mj12bot", "dotbot", "petalbot",
    # CLI / scripts (also catches our own curl tests)
    "curl", "wget", "python-requests", "python-urllib", "httpx", "go-http-client",
    # Social-card unfurlers
    "facebookexternalhit", "twitterbot", "linkedinbot", "slackbot", "whatsapp",
    # Monitors
    "uptimerobot", "pingdom", "statuscake", "site24x7",
    # Headless browsers (often automated scraping)
    "headlesschrome", "phantomjs",
)


def is_bot(user_agent: str) -> bool:
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    return any(p in ua_lower for p in BOT_PATTERNS)


def hash_ip(ip: str, salt: str) -> str:
    """Salted SHA-256 of the visitor IP. Stable across days (same salt).

    Returns the 64-char hex digest. A placeholder hash is returned when IP is unknown,
    so the `ip_hash` column is never null and per-visitor counts don't break.
    """
    if not ip:
        return "0" * 64
    return hashlib.sha256(f"{salt}:{ip}".encode("utf-8")).hexdigest()


def enrich(event: Dict[str, Any], salt: str) -> Dict[str, Any]:
    """Add `ip_hash` + `is_bot`, then drop raw IPs from the event."""
    # Prefer real visitor IP (Cloudflare-injected); fall back to remote_addr for local tests.
    real_ip = event.get("_cf_connecting_ip") or event.get("_remote_addr") or ""
    event["ip_hash"] = hash_ip(real_ip, salt)
    event["is_bot"] = is_bot(event.get("user_agent", ""))
    # Drop raw IPs — they never reach the database.
    event.pop("_cf_connecting_ip", None)
    event.pop("_remote_addr", None)
    return event
