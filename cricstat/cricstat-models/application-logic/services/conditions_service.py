"""Match conditions the simulator needs that Cricsheet can't give: how often an ODI ends without a
result (including fixtures abandoned without a ball, which Cricsheet doesn't publish) and how often
it's tied. Source: every ODI on Wikipedia's season pages (cached), the same pages the Afghanistan
supplement uses.

no-result rate for a host country in a season =
    (no results there + k * global rate) / (matches + k):
a few dozen matches per country and season are too few to trust alone, so they're shrunk toward the
global rate (k = SHRINK). Everything is computed from matches before `until` (no leakage).
"""
import datetime
from typing import Dict, Iterable, List, Optional

from application_logic.services.supplement_service import season_titles
from db_logic.repository import serving_reader
from db_logic.repository import supplement_store as store
from db_logic.sources import season_pages
from db_logic.sources.wikipedia import WikipediaClient

SHRINK = 50.0


def odi_rows(cfg, client: Optional[WikipediaClient] = None,
             today: Optional[datetime.date] = None) -> List[dict]:
    """Every ODI with a result on the season pages up to today's season, de-duplicated (scorecard
    id or ODI no. + date), with its venue country."""
    client = client or WikipediaClient(cfg)
    cities = serving_reader.city_countries(cfg.VENUE_MAP)
    cities.update(store.venue_overrides(cfg.SUPPLEMENT_DIR))
    seen, out = set(), []
    for title in season_titles(today or datetime.date.today()):
        page = client.page(title)
        if page.get("missing"):
            continue
        for r in season_pages.parse_page(title, page["wikitext"]):
            if not r["result"]:
                continue
            key = (r["match_id"] or r["odi_no"], r["date"])
            if key in seen:
                continue
            seen.add(key)
            city = r["venue"].rsplit(",", 1)[-1].strip()
            r["venue_country"] = cities.get(city)
            out.append(r)
    return out


def rates(rows: Iterable[dict], until: str, countries: Iterable[str], months: Iterable[int],
          shrink: float = SHRINK) -> Dict[str, object]:
    """{'global': p, 'tie': p, 'by_country': {country: p}, 'counts': {...}} from matches before
    `until`; by_country uses only the given months (the tournament's season)."""
    months = set(months)
    rows = [r for r in rows if r["date"] < until]
    n = len(rows)
    nr = sum(1 for r in rows if r["result"] == "no_result")
    ties = sum(1 for r in rows if r["result"] == "tie")
    g = nr / n if n else 0.0
    out, counts = {}, {}
    for c in countries:
        sel = [r for r in rows if r["venue_country"] == c and int(r["date"][5:7]) in months]
        k = sum(1 for r in sel if r["result"] == "no_result")
        out[c] = (k + shrink * g) / (len(sel) + shrink)
        counts[c] = {"matches": len(sel), "no_results": k}
    return {"global": g, "tie": ties / (n - nr) if n > nr else 0.0, "by_country": out,
            "counts": counts, "matches": n}
