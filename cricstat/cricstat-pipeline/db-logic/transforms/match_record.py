"""Turn one Cricsheet match file (raw bytes) into a matches_raw record.

The stored blob is the file's exact bytes, zlib-compressed; nothing is re-serialised,
so the sha256 stays comparable across downloads.
"""
import hashlib
import json
import zlib
from typing import Optional

REQUIRED_KEYS = ("info", "innings")


class MatchParseError(ValueError):
    """The file is not a usable Cricsheet match (bad JSON, missing keys, wrong shape)."""


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _str_or_none(value) -> Optional[str]:
    return value if isinstance(value, str) else None


def parse_match(raw: bytes) -> dict:
    """Parse and validate. Raises MatchParseError if the file can't be stored."""
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise MatchParseError("invalid JSON: %s" % exc) from exc
    if not isinstance(doc, dict):
        raise MatchParseError("top level is %s, not an object" % type(doc).__name__)
    missing = [k for k in REQUIRED_KEYS if k not in doc]
    if missing:
        raise MatchParseError("missing keys: %s" % ", ".join(missing))
    if not isinstance(doc["info"], dict):
        raise MatchParseError("info is not an object")
    return doc


def build_record(match_id: str, raw: bytes, sha256: Optional[str] = None) -> dict:
    """Validate the file and extract the indexed metadata columns."""
    doc = parse_match(raw)
    info, meta = doc["info"], doc.get("meta") or {}
    dates = info.get("dates") or []
    teams = info.get("teams")
    event = info.get("event")
    revision = meta.get("revision") if isinstance(meta, dict) else None
    return {
        "match_id": match_id,
        "sha256": sha256 or sha256_hex(raw),
        "json_zlib": zlib.compress(raw, 6),
        "json_bytes": len(raw),
        "data_version": _str_or_none(meta.get("data_version")) if isinstance(meta, dict) else None,
        "revision": revision if isinstance(revision, int) else None,
        "match_type": _str_or_none(info.get("match_type")),
        "gender": _str_or_none(info.get("gender")),
        "team_type": _str_or_none(info.get("team_type")),
        "start_date": min(d for d in dates if isinstance(d, str)) if any(
            isinstance(d, str) for d in dates) else None,
        "teams": json.dumps(teams, ensure_ascii=False) if isinstance(teams, list) else None,
        "event_name": _str_or_none(event.get("name")) if isinstance(event, dict) else None,
    }


def decompress(blob: bytes) -> bytes:
    """Inverse of the stored json_zlib."""
    return zlib.decompress(blob)
