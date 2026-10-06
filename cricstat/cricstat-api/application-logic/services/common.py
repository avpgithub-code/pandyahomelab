"""Shared helpers: filter parsing (F5 §2 common filters), paging, catalog lookups, team slugs."""
import re
from typing import Dict, List, Optional, Tuple

from application_logic.services.slugs import TeamSlugs
from db_logic.repository import meta_repo, teams_repo
from db_logic.repository.db import ServingDB
from shared.exceptions import BadFilter

DEFAULT_LIMIT, MAX_LIMIT = 20, 100
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_YEAR = re.compile(r"^\d{4}$")
_SEASON = re.compile(r"^(\d{4})-(\d{2})$")


def team_slugs(db: ServingDB) -> TeamSlugs:
    return db.cached("team_slugs", lambda: TeamSlugs(teams_repo.all_teams(db)))


def catalog_defs(db: ServingDB, keys: List[Tuple[str, str]]) -> Dict[str, str]:
    """Descriptions from semantic_catalog for (object, column) pairs, keyed by column (or object
    when column is '')."""
    cat = db.cached("catalog", lambda: {(r["object_name"], r["column_name"]): r["description"]
                                        for r in meta_repo.catalog(db)})
    out = {}
    for obj, col in keys:
        if (obj, col) in cat:
            label = col or obj
            if col and col in out:          # e.g. average for batting and bowling
                label = "%s.%s" % (obj.replace("v_player_", ""), col)
            out[label] = cat[(obj, col)]
    return out


def _bound(value: str, end: bool) -> str:
    """ISO date, a year (2023) or a season (2023-24: 1 Jul 2023 – 30 Jun 2024)."""
    if _DATE.match(value):
        return value
    if _YEAR.match(value):
        return "%s-12-31" % value if end else "%s-01-01" % value
    m = _SEASON.match(value)
    if m and (int(m.group(1)) + 1) % 100 == int(m.group(2)):
        return "%d-06-30" % (int(m.group(1)) + 1) if end else "%s-07-01" % m.group(1)
    raise BadFilter("dates are YYYY-MM-DD, a year (2023) or a season (2023-24); got %r" % value)


def dates(date_from: Optional[str], date_to: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    f = _bound(date_from, False) if date_from else None
    t = _bound(date_to, True) if date_to else None
    if f and t and f > t:
        raise BadFilter("from (%s) is after to (%s)" % (f, t))
    return f, t


def page(limit: Optional[int], offset: Optional[int]) -> Tuple[int, int]:
    limit = DEFAULT_LIMIT if limit is None else limit
    offset = offset or 0
    if not 1 <= limit <= MAX_LIMIT:
        raise BadFilter("limit must be 1–%d" % MAX_LIMIT)
    if offset < 0:
        raise BadFilter("offset must be ≥ 0")
    return limit, offset


def gender(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if value not in ("male", "female"):
        raise BadFilter("gender is male or female")
    return value
