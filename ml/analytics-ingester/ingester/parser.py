"""Parse one Nginx JSON access-log line into a typed event dict."""
import json
from datetime import datetime
from typing import Dict, Any


def parse_line(line: str) -> Dict[str, Any]:
    """Parse a single JSON line from Nginx's json_combined log format."""
    raw = json.loads(line)

    country = (raw.get("cf_country") or "").upper()
    if len(country) != 2 or country in ("XX", "T1"):  # Cloudflare 'unknown' codes
        country = None

    return {
        "occurred_at":      datetime.fromisoformat(raw["timestamp"]),
        # Raw IPs — enricher will hash and drop these
        "_remote_addr":     raw.get("remote_addr") or None,
        "_cf_connecting_ip": raw.get("cf_connecting_ip") or None,
        "country":          country,
        "method":           (raw.get("method") or "").upper()[:8],
        "path":             raw.get("path") or "",
        "status_code":      int(raw.get("status") or 0),
        "bytes_sent":       int(raw.get("bytes_sent") or 0),
        "response_time_ms": int(round(float(raw.get("request_time") or 0) * 1000)),
        "referrer":         raw.get("referrer") or None,
        "user_agent":       raw.get("user_agent") or None,
    }
