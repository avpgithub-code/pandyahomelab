"""What search engines get for each player and team page (P0.6).

The pages themselves are the static shells in cricstat/web, filled in by JavaScript. For search
engines and link previews the API fills in the page's own title, description, canonical URL,
robots rule, JSON-LD and a short summary of real numbers (presentation-logic/api/pages.py turns
this data into HTML). Thin pages stay usable but get noindex, so they don't count against the site.
"""
from typing import Dict, List, Optional

from application_logic.services.common import team_slugs
from application_logic.services.golden import trunc2
from application_logic.services.meta_service import SCOPE_LABELS
from application_logic.services.players_service import derive_role
from application_logic.services.slugs import GENDER, full_name, player_slug
from db_logic.repository import pages_repo, players_repo, teams_repo
from db_logic.repository.db import ServingDB

FORMAT_ORDER = ("ODI", "T20I", "TEST")                 # the site's format order everywhere
FORMAT_LABEL = dict(SCOPE_LABELS, TEST="Test")
FORMAT_PLURAL = {"ODI": "ODIs", "T20I": "T20Is", "TEST": "Tests",
                 "T20_LEAGUE": "T20 league matches"}
LEAGUE_SHORT = {"ipl": "IPL", "wpl": "WPL", "bbl": "BBL", "wbbl": "WBBL", "psl": "PSL",
                "cpl": "CPL", "sa20": "SA20", "mlc": "MLC", "t20-blast": "T20 Blast",
                "the-hundred-men": "The Hundred", "the-hundred-women": "The Hundred"}
MAX_LEAGUE_ROWS = 2


def _num(n) -> str:
    return f"{n or 0:,}"


def _ratio(v) -> str:
    return "-" if v is None else trunc2(v)


def _join(items: List[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " & " + items[-1]


def _years(first: Optional[str], last: Optional[str]) -> str:
    if not first:
        return ""
    a, b = first[:4], (last or first)[:4]
    return a if a == b else "%s–%s" % (a, b)


def indexable(scopes: List[dict], min_intl: int, min_league: int) -> bool:
    by = {s["scope"]: s["matches"] or 0 for s in scopes}
    return (sum(by.get(k, 0) for k in pages_repo.INTL) >= min_intl
            or by.get("LEAGUES", 0) >= min_league)


def player_page(db: ServingDB, slug: str, min_intl: int, min_league: int) -> dict:
    """{'status': 404} | {'status': 301, 'slug': canonical} | {'status': 200, ...page data}."""
    player_id = slug.rsplit("-", 1)[-1]
    p = players_repo.identity(db, player_id) if len(player_id) == 8 else None
    if p is None:
        return {"status": 404}
    canonical = player_slug(p["name"], p["player_id"])
    if slug != canonical:
        return {"status": 301, "slug": canonical}
    key = p["player_key"]
    name = full_name(p["name"], pages_repo.name_variants(db, key))
    scopes = players_repo.scopes_played(db, key)
    by_scope = {s["scope"]: s for s in scopes}
    gender = scopes[0]["gender"] if scopes else None
    slugs = team_slugs(db)
    teams = players_repo.teams(db, key)
    main = next((t for t in teams if t["team_type"] == "international"),
                teams[0] if teams else None)
    team = None if main is None else {
        "name": main["name"], "slug": slugs.find(main["name"], main["gender"], main["team_type"]),
        "team_type": main["team_type"]}
    basis = "ALL" if "ALL" in by_scope else (scopes[0]["scope"] if scopes else None)
    role = derive_role(players_repo.career(db, key, basis)) if basis else None

    leagues = sorted((s for s in scopes if s["scope"] in LEAGUE_SHORT),
                     key=lambda s: -(s["matches"] or 0))[:MAX_LEAGUE_ROWS]
    rows = []
    for scope in [f for f in FORMAT_ORDER if f in by_scope] + [s["scope"] for s in leagues]:
        c = players_repo.career(db, key, scope)
        bat, bowl = c["batting"] or {}, c["bowling"] or {}
        rows.append({"scope": scope, "label": FORMAT_LABEL.get(scope) or LEAGUE_SHORT[scope],
                     "matches": by_scope[scope]["matches"], "runs": bat.get("runs"),
                     "bat_avg": bat.get("average"), "strike_rate": bat.get("strike_rate"),
                     "hundreds": bat.get("hundreds"), "fifties": bat.get("fifties"),
                     "wickets": bowl.get("wickets"), "bowl_avg": bowl.get("average"),
                     "economy": bowl.get("economy")})

    intl = [r for r in rows if r["scope"] in FORMAT_ORDER]
    labels = [r["label"] for r in intl] or [r["label"] for r in rows[:1]]
    if intl and leagues and len(labels) < 3:
        labels.append(LEAGUE_SHORT[leagues[0]["scope"]])
    title = "%s — %s stats & career by year | cricstat" % (name, _join(labels)) if labels \
        else "%s — cricket stats | cricstat" % name

    span = _years(min((s["first_date"] for s in scopes), default=None),
                  max((s["last_date"] for s in scopes), default=None))
    who = ", ".join(x for x in (team["name"] + (" women" if gender == "female" else "")
                                if team else None, role) if x)
    played = _join(["%s %s" % (_num(r["matches"]),
                               FORMAT_PLURAL.get(r["scope"], r["label"] + " matches"))
                    for r in (intl or rows)]) if rows else ""
    desc = "%s%s: %s%s." % (name, " (%s)" % who if who else "", played,
                            " (%s)" % span if span else "")
    top = max(intl or rows, key=lambda r: r["matches"] or 0) if rows else None
    if top:
        bits = []
        if role != "bowler" and top["runs"]:
            bits.append("%s runs at %s" % (_num(top["runs"]), _ratio(top["bat_avg"])))
        if role in ("bowler", "all-rounder") and top["wickets"]:
            bits.append("%s wickets at %s" % (_num(top["wickets"]), _ratio(top["bowl_avg"])))
        if bits:
            desc += " %s: %s." % (top["label"], " and ".join(bits))
    desc += " Career by year, phase and opponent, from ball-by-ball data."
    return {"status": 200, "slug": canonical, "name": name, "scorecard_name": p["name"],
            "gender": gender, "role": role, "team": team, "span": span, "rows": rows,
            "title": title, "description": desc, "wikidata_qid": p["wikidata_qid"],
            "indexable": indexable(scopes, min_intl, min_league)}


def team_label(t: dict) -> str:
    return "%s %s" % (t["name"], GENDER.get(t["gender"], t["gender"]))


def team_page(db: ServingDB, slug: str, min_intl: int) -> dict:
    t = team_slugs(db).get(slug)
    if t is None:
        return {"status": 404}
    rows = [r for r in teams_repo.record(db, t["team_key"], None) if r["matches"]]
    official = [r for r in rows if r["format_key"] in FORMAT_ORDER]
    official.sort(key=lambda r: FORMAT_ORDER.index(r["format_key"]))
    shown = official if t["team_type"] == "international" else rows
    label = team_label(t)
    possessive = "%s %s's" % (t["name"], GENDER.get(t["gender"], ""))
    kind = "cricket team" if t["team_type"] == "international" else "team"
    fmts = _join([FORMAT_LABEL.get(r["format_key"], r["format_key"]) for r in official]) \
        if official else "match"
    title = "%s %s — %s record & results | cricstat" % (possessive, kind, fmts)
    desc = "%s record by format from ball-by-ball data: %s." % (
        possessive, _join(["%s %s (won %s%%)" % (_num(r["matches"]),
                                                FORMAT_PLURAL.get(r["format_key"], r["format_key"]),
                                                _ratio(r["win_pct"])) for r in shown[:3]])
        if shown else "no completed matches yet")
    desc += " Recent results, head to head, home and away, results by year and top performers."
    return {"status": 200, "slug": slug, "name": label, "team_name": t["name"],
            "gender": t["gender"], "team_type": t["team_type"],
            "span": _years(t["first_date"], t["last_date"]),
            "rows": [{"label": FORMAT_LABEL.get(r["format_key"], r["format_key"]),
                      **{k: r[k] for k in ("matches", "won", "lost", "tied", "drawn", "no_result",
                                           "win_pct")}} for r in shown],
            "title": title, "description": desc,
            "indexable": t["team_type"] == "international"
            and sum(r["matches"] for r in official) >= min_intl}


def sitemap_entries(db: ServingDB, min_intl: int, min_league: int) -> List[Dict[str, str]]:
    """[{'path', 'lastmod'}] for every page worth indexing: players by the indexable rule and
    international teams with min_intl official matches."""
    out = [{"path": "players/%s/" % player_slug(r["name"], r["player_id"]),
            "lastmod": r["last_date"]}
           for r in pages_repo.indexable_players(db, min_intl, min_league)]
    for slug, t in sorted(team_slugs(db).by_slug.items()):
        if t["team_type"] != "international" or not t["matches"]:
            continue
        n = sum(r["matches"] for r in teams_repo.record(db, t["team_key"], None)
                if r["format_key"] in FORMAT_ORDER)
        if n >= min_intl:
            out.append({"path": "countries/%s/" % slug, "lastmod": t["last_date"]})
    return out
