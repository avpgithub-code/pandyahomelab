"""Afghanistan results supplement: draft from Wikipedia, check, and propose changes.

    draft  → season pages ("International cricket in <season>") give one row per Afghanistan ODI;
             each row is cross-checked against the series/tournament article's match box (an
             independently edited source); the team article's "ODI record versus other nations"
             table becomes the checksum (afg_totals.csv).
    check  → re-draft into a temporary folder and diff against the committed files. It never edits
             the committed files: anyone can edit Wikipedia, so a change only goes live through a
             reviewed commit and a models-image publish (P1 plan §6, audit §6).

Review decisions already in the committed CSV (check_status 'accepted' + note) are carried over to
an unchanged row, so the weekly check proposes only what really changed.
"""
import datetime
import os
import re
import tempfile
from typing import Dict, List, Optional, Tuple

from application_logic.quality import supplement_checks as checks
from db_logic.repository import serving_reader
from db_logic.repository import supplement_store as store
from db_logic.sources import match_boxes, season_pages
from db_logic.sources.wikipedia import WikipediaClient
from shared.logger import get_logger

log = get_logger("supplement")

AFG = checks.AFG
TEAM_ARTICLE = "Afghanistan national cricket team"
# Sub-articles of a tournament page that hold its match boxes.
SUB_ARTICLE_WORDS = ("group", "stage", "knockout", "super", "final", "round", "pool")
_CONTENT = ("start_date", "team1", "team2", "venue_country", "result", "winner", "has_play")


def season_titles(today: datetime.date) -> List[str]:
    """Every season page that can hold an Afghanistan ODI (first ODI: April 2009)."""
    titles = ["International cricket in 2008–09"]
    for y in range(2009, today.year + 1):
        titles += ["International cricket in %d" % y,
                   "International cricket in %d–%02d" % (y, (y + 1) % 100)]
    return titles


def _city(venue: str) -> str:
    return venue.rsplit(",", 1)[-1].strip() if "," in venue else venue.strip()


def _draft_rows(client: WikipediaClient, codes: Dict[str, str], cities: Dict[str, str],
                serving_ids, today) -> Tuple[List[dict], List[str]]:
    issues: List[str] = []
    found: Dict[Tuple[str, frozenset], dict] = {}
    revids: Dict[str, object] = {}
    for title in season_titles(today):
        page = client.page(title)
        if page.get("missing"):
            continue
        revids[title] = page["revid"]
        for r in season_pages.parse_page(title, page["wikitext"]):
            t1, t2 = codes.get(r["team1"] or ""), codes.get(r["team2"] or "")
            if AFG not in (t1, t2):
                if AFG in (r["team1"], r["team2"]):
                    issues.append("unmapped team token in %s ODI %s" % (title, r["odi_no"]))
                continue
            if t1 is None or t2 is None:
                issues.append("ODI %s (%s): unmapped team %r/%r — add it to team_codes.csv"
                              % (r["odi_no"], r["date"], r["team1"], r["team2"]))
                continue
            if not r["result"]:
                continue                      # cancelled before the day, or not played yet
            key = (r["match_id"] or "odi-%s" % r["odi_no"], frozenset((t1, t2)))
            if key in found:
                continue                      # the same match listed on two season pages
            r.update(team1=t1, team2=t2, winner=codes.get(r["winner"] or "") or None,
                     source_revid=revids[title])
            found[key] = r
    rows = []
    ids_seen: Dict[str, str] = {}
    for (_, _teams), r in sorted(found.items(), key=lambda kv: kv[1]["date"]):
        mid = r["match_id"]
        if mid and serving_ids is not None and mid in serving_ids:
            issues.append("ODI %s %s: the linked scorecard id %s belongs to a match in the"
                          " serving DB (a wrong link on Wikipedia, or Cricsheet restored it);"
                          " keyed by ODI number"
                          % (r["odi_no"], r["date"], mid))
            mid = None
        if mid and mid in ids_seen:
            issues.append("ODI %s: scorecard id %s also used by %s — keyed by ODI number"
                          % (r["odi_no"], mid, ids_seen[mid]))
            mid = None
        if mid:
            ids_seen[mid] = "ODI %s" % r["odi_no"]
        city = _city(r["venue"])
        country = cities.get(city)
        if not country:
            issues.append("ODI %s (%s): no country for city %r — add it to supplement_venues.csv"
                          % (r["odi_no"], r["date"], city))
        rows.append({
            "match_key": mid or "odi-%s" % r["odi_no"], "match_id": mid, "odi_no": r["odi_no"],
            "start_date": r["date"], "team1": r["team1"], "team2": r["team2"],
            "venue": r["venue"], "city": city, "venue_country": country,
            "result": r["result"], "winner": r["winner"] if r["result"] != "no_result" else None,
            "method": r["method"], "decided_by": r["decided_by"], "has_play": r["has_play"],
            "margin": r["margin"], "source_page": r["source_title"],
            "source_revid": r["source_revid"], "check_article": r.get("article"),
            "check_status": None, "note": None,
        })
    return rows, issues


def _second_source(client: WikipediaClient, rows: List[dict], codes: Dict[str, str]) -> None:
    """Compare each row with the match box in its series/tournament article (and the article's
    sub-articles, e.g. '2023 Cricket World Cup group stage'). Sets check_status."""
    boxes_by_article: Dict[str, List[dict]] = {}

    def boxes(title: str) -> List[dict]:
        if title not in boxes_by_article:
            page = client.page(title)
            found = match_boxes.parse_boxes(page.get("wikitext", ""))
            for sub in match_boxes.sub_articles(page.get("wikitext", ""))[:6]:
                if sub != title and any(w in sub.lower() for w in SUB_ARTICLE_WORDS):
                    found += match_boxes.parse_boxes(client.page(sub).get("wikitext", ""))
            boxes_by_article[title] = found
        return boxes_by_article[title]

    for r in rows:
        if not r["check_article"]:
            opp = r["team2"] if r["team1"] == AFG else r["team1"]
            r["check_article"] = client.search_title(
                'Afghan cricket team %s %s ODI' % (opp, r["start_date"][:4]),
                must=("afghan", r["start_date"][:4]))
        if not r["check_article"]:
            r["check_status"] = "no_article"
            continue
        cands = boxes(r["check_article"])
        box = next((b for b in cands if r["match_id"] and b["match_id"] == r["match_id"]), None)
        if box is None:
            box = next((b for b in cands if match_boxes.same_date(b["date"], r["start_date"]) and
                        {codes.get(b["team1"] or ""), codes.get(b["team2"] or "")}
                        == {r["team1"], r["team2"]}), None)
        if box is None:
            r["check_status"] = "not_found"
            continue
        out = match_boxes.box_outcome(box["result_text"], codes)
        same_teams = {codes.get(box["team1"] or ""), codes.get(box["team2"] or "")} == \
            {r["team1"], r["team2"]}
        same_result = out["result"] == r["result"] and \
            (r["result"] != "win" or out["winner"] == r["winner"])
        if match_boxes.same_date(box["date"], r["start_date"]) and same_teams and same_result:
            r["check_status"] = "confirmed"
        else:
            r["check_status"] = "differs"
            r["note"] = "match box: %s, %s v %s, %s" % (box["date"], box["team1"], box["team2"],
                                                        box["result_text"][:60])


def _totals(client: WikipediaClient, codes: Dict[str, str]) -> List[dict]:
    """The team article's 'ODI record versus other nations' table → checksum rows."""
    page = client.page(TEAM_ARTICLE)
    w = page["wikitext"]
    i = w.find("ODI record versus other nations")
    if i < 0:
        raise ValueError("no 'ODI record versus other nations' table in %r" % TEAM_ARTICLE)
    table = w[i:w.find("|}", i)]
    as_of = re.search(r"correct as of (.+?)'*\s*<ref", w[i:i + len(table) + 600])
    out = []
    for m in re.finditer(r"!\s*scope=row\s*\|(.+?)\n\|\s*([^\n]+)", table):
        toks = season_pages.team_tokens(m.group(1))
        nums = [x.strip() for x in m.group(2).split("||")]
        out.append({"opponent": codes.get(toks[0], toks[0]) if toks else m.group(1).strip(),
                    "matches": nums[0], "won": nums[1], "lost": nums[2], "tied": nums[3],
                    "no_result": nums[4]})
    tm = re.search(r"Total'*\s*\n\|'*(\d+)'*\|\|'*(\d+)'*\|\|'*(\d+)'*\|\|'*(\d+)'*\|\|'*(\d+)",
                   table)
    if tm:
        out.append(dict(zip(("opponent", "matches", "won", "lost", "tied", "no_result"),
                            ("TOTAL",) + tm.groups())))
    stamp = re.sub(r"\{\{cr\|([A-Z]+)\}\}", r"\1", as_of.group(1)) if as_of else ""
    stamp = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", stamp)
    stamp = re.sub(r"['{}]+", "", stamp).strip()
    for r in out:
        r.update(source_page=TEAM_ARTICLE, source_revid=page["revid"], as_of=stamp)
    return out


def _carry_over(rows: List[dict], committed: List[Dict[str, str]]) -> None:
    """Keep a reviewer's 'accepted' + note on rows whose content hasn't changed."""
    old = {r["match_key"]: r for r in committed}
    for r in rows:
        o = old.get(r["match_key"])
        if o and o["check_status"] == "accepted" and r["check_status"] != "confirmed" and \
                all(str(r[k] or "") == o[k] for k in _CONTENT):
            r["check_status"], r["note"] = "accepted", o["note"]


def draft(cfg, out_dir: Optional[str] = None, client: Optional[WikipediaClient] = None,
          today: Optional[datetime.date] = None) -> Dict[str, object]:
    """Build afg_odi_results.csv + afg_totals.csv into out_dir (default: the supplement folder)."""
    out_dir = out_dir or cfg.SUPPLEMENT_DIR
    client = client or WikipediaClient(cfg, max_age_s=cfg.WIKI_CACHE_MAX_AGE_S)
    today = today or datetime.date.today()
    codes = store.team_codes(cfg.SUPPLEMENT_DIR)
    cities = serving_reader.city_countries(cfg.VENUE_MAP)
    cities.update(store.venue_overrides(cfg.SUPPLEMENT_DIR))
    serving_ids = None
    if os.path.exists(cfg.SERVING_DB):
        with serving_reader.connect(cfg.SERVING_DB) as conn:
            serving_ids = serving_reader.all_match_ids(conn)
    rows, issues = _draft_rows(client, codes, cities, serving_ids, today)
    _second_source(client, rows, codes)
    committed_path = os.path.join(cfg.SUPPLEMENT_DIR, store.RESULTS_FILE)
    if os.path.exists(committed_path):
        _carry_over(rows, store.read_results(cfg.SUPPLEMENT_DIR))
    totals = _totals(client, codes)
    os.makedirs(out_dir, exist_ok=True)
    store.write_results(out_dir, rows)
    store.write_totals(out_dir, totals)
    written = store.read_results(out_dir)
    status: Dict[str, int] = {}
    for r in written:
        status[r["check_status"]] = status.get(r["check_status"], 0) + 1
    return {"rows": len(written), "played": sum(1 for r in written if r["has_play"] == "1"),
            "check_status": status, "issues": issues,
            "totals_errors": checks.check_totals(written, store.read_totals(out_dir)),
            "out_dir": out_dir}


def propose(cfg, client: Optional[WikipediaClient] = None) -> Dict[str, object]:
    """Weekly check: draft into a temporary folder and diff with the committed files."""
    committed = {r["match_key"]: r for r in store.read_results(cfg.SUPPLEMENT_DIR)}
    with tempfile.TemporaryDirectory() as tmp:
        summary = draft(cfg, out_dir=tmp, client=client)
        fresh = {r["match_key"]: r for r in store.read_results(tmp)}
        totals = store.read_totals(tmp)
    added = sorted(k for k in fresh if k not in committed)
    removed = sorted(k for k in committed if k not in fresh)
    changed = sorted(k for k in fresh if k in committed and
                     any(fresh[k][c] != committed[k][c] for c in _CONTENT))
    total_row = next((t for t in totals if t["opponent"] == "TOTAL"), {})
    return {"added": [fresh[k] for k in added], "removed": [committed[k] for k in removed],
            "changed": [{"match_key": k,
                         "was": {c: committed[k][c] for c in _CONTENT},
                         "now": {c: fresh[k][c] for c in _CONTENT}} for k in changed],
            "published_total": total_row, "issues": summary["issues"],
            "totals_errors": summary["totals_errors"],
            "up_to_date": not (added or removed or changed)}
