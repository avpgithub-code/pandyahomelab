"""Tournament configs: draft them from Wikipedia (reviewed before commit) and validate them.

    draft_past(…)  WC 2019 / 2023: fixtures and actual results from the season pages (every
                   ODI incl. matches abandoned without a ball, which Cricsheet doesn't publish),
                   final standings
                   from the points-table template, each played match cross-checked against the
                   serving DB (Cricsheet) or the Afghanistan supplement.
    draft_2027(…)  WC 2027: the published schedule (57 match boxes incl. scorecard ids) with
                   placeholders for qualifier slots and later stages.
    validate(…)    structural checks every load runs (and CI): slots resolve, round robins are
                   complete, knockout slots exist, team names are cricstat names.
"""
import collections
import re
from typing import Dict, List, Optional, Tuple

from db_logic.repository import serving_reader, supplement_store, tournament_store
from db_logic.sources import match_boxes, season_pages
from db_logic.sources.wikipedia import WikipediaClient
from shared.exceptions import DataCheckError

_SLOT = re.compile(r"^(?:[A-Z]\d|L\d+|4TH|S7-\d|SS-\d|W\d+|Q[1-4]|QA|QB|SSW)$")
_START_DATE = re.compile(
    r"\{\{\s*Start date\s*\|[^|}]*?\|?\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})")


def _cities(cfg) -> Dict[str, str]:
    cities = serving_reader.city_countries(cfg.VENUE_MAP)
    cities.update(supplement_store.venue_overrides(cfg.SUPPLEMENT_DIR))
    return cities


def _city(venue: str) -> str:
    return venue.rsplit(",", 1)[-1].strip() if "," in venue else venue.strip()


def standings(client: WikipediaClient, template: str,
              codes: Dict[str, str]) -> Tuple[List[str], object]:
    """Final positions from a 'Sports table' points-table template: team1=IND |team2=AUS …"""
    page = client.page(template)
    pos = sorted(((int(n), c) for n, c in re.findall(r"\|\s*team(\d+)\s*=\s*([A-Za-z]+)",
                                                     page["wikitext"])))
    return [codes[c] for _, c in pos], page["revid"]


# -- past tournaments --------------------------------------------------------------------------
def draft_past(cfg, tid: str, meta: Dict[str, object], client: Optional[WikipediaClient] = None
               ) -> Dict[str, object]:
    """meta: name, start, end, hosts, season_titles, points_table, knockout (n semis), sources."""
    client = client or WikipediaClient(cfg)
    codes = supplement_store.team_codes(cfg.SUPPLEMENT_DIR)
    cities = _cities(cfg)
    rows = []
    for title in meta["season_titles"]:
        page = client.page(title)
        for r in season_pages.parse_page(title, page["wikitext"]):
            if meta["start"] <= r["date"] <= meta["end"] and "World Cup" in r["section"]:
                r["source_revid"] = page["revid"]
                rows.append(r)
    seen, uniq = set(), []
    for r in sorted(rows, key=lambda r: (r["date"], r["odi_no"])):
        key = (r["odi_no"], r["date"])
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    table, table_rev = standings(client, meta["points_table"], codes)
    n = len(uniq)
    fixtures = []
    for i, r in enumerate(uniq, start=1):
        t1, t2 = codes[r["team1"]], codes[r["team2"]]
        winner = codes.get(r["winner"] or "")
        stage, s1, s2 = "league", t1, t2
        if i == n:
            stage, s1, s2 = "final", "W%d" % (n - 2), "W%d" % (n - 1)
        elif i >= n - 2:
            stage = "semi"
            s1, s2 = ("L1", "L4") if i == n - 2 else ("L2", "L3")
        city = _city(r["venue"])
        fixtures.append({
            "match_no": i, "stage": stage, "group": "L" if stage == "league" else "",
            "date": r["date"], "slot1": s1, "slot2": s2, "venue": r["venue"], "city": city,
            "venue_country": cities.get(city), "match_key": r["match_id"] or "odi-%s" % r["odi_no"],
            "team1": t1, "team2": t2, "result": r["result"],
            "winner": winner if r["result"] in ("win", "tie") else None,
            "has_play": r["has_play"]})
    fmt = {
        "id": tid, "name": meta["name"], "start": meta["start"], "end": meta["end"],
        "hosts": meta["hosts"], "teams": sorted({f["team1"] for f in fixtures} |
                                                {f["team2"] for f in fixtures}),
        "points": {"win": 2, "tie": 1, "no_result": 1},
        "stages": [
            {"id": "league", "kind": "round_robin", "groups": {"L": table},
             "advance": {"top": 4}, "tie": "points_shared"},
            {"id": "semi", "kind": "knockout", "washout": "higher_placed", "tie": "super_over"},
            {"id": "final", "kind": "knockout", "washout": "shared", "tie": "super_over"},
        ],
        "tiebreakers": ["points", "wins", "nrr", "head_to_head"],
        "final_standings": {"L": table},
        "sources": meta["sources"] + ["%s (revision %s)" % (meta["points_table"], table_rev)],
        "assumptions": [
            "NRR is not simulated (no margins); in a replay the official final standings settle "
            "ties, in a forecast equal points and wins are split by a random draw.",
        ],
    }
    return {"format": fmt, "fixtures": fixtures}


def verify_past(cfg, fixtures: List[Dict[str, object]]) -> List[str]:
    """Every played match must agree with Cricsheet (or the supplement for Afghanistan)."""
    problems = []
    supp = {r["match_key"]: r for r in supplement_store.read_results(cfg.SUPPLEMENT_DIR)}
    with serving_reader.connect(cfg.SERVING_DB) as conn:
        db = {r["match_id"]: r for r in serving_reader.men_odi_results(conn)}
    for f in fixtures:
        key = str(f["match_key"])
        if "Afghanistan" in (f["team1"], f["team2"]):
            ref = supp.get(key)
            src = "supplement"
        elif str(f["has_play"]) == "0":
            continue                  # abandoned without a ball: not in Cricsheet, by design
        else:
            ref = db.get(key)
            src = "Cricsheet"
        if ref is None:
            problems.append("match %s %s %s v %s: not found in %s" % (
                f["match_no"], f["date"], f["team1"], f["team2"], src))
            continue
        same = (ref["start_date"] == f["date"] and {ref["team1"], ref["team2"]} ==
                {f["team1"], f["team2"]} and ref["result"] == f["result"] and
                (ref["winner"] or None) == (f["winner"] or None))
        if not same:
            problems.append("match %s: fixture %s %s v %s %s/%s, %s says %s %s v %s %s/%s" % (
                f["match_no"], f["date"], f["team1"], f["team2"], f["result"], f["winner"], src,
                ref["start_date"], ref["team1"], ref["team2"], ref["result"], ref["winner"]))
    return problems


# -- 2027 ----------------------------------------------------------------------------------------
def _slot_2027(raw: str, codes: Dict[str, str]) -> str:
    toks = season_pages.team_tokens(raw)
    if toks and toks[0] in codes:
        return codes[toks[0]]
    text = re.sub(r"\{\{[^}]*\}\}", "", raw).strip()
    low = text.lower()
    if low == "qualifier a":
        return "QA"
    if low == "qualifier b":
        return "QB"
    if text in ("A4/B4", "B4/A4"):
        return "4TH"
    m = re.match(r"^(first|second|third|fourth) placed team$", low)
    if m:
        return "S7-%d" % ("first second third fourth".split().index(m.group(1)) + 1)
    m = re.match(r"^winner of (?:semi-final|match) (\d+)$", low)
    if m:
        return "W%s" % m.group(1)
    return text


def draft_2027(cfg, client: Optional[WikipediaClient] = None) -> Dict[str, object]:
    client = client or WikipediaClient(cfg, max_age_s=cfg.WIKI_CACHE_MAX_AGE_S)
    codes = supplement_store.team_codes(cfg.SUPPLEMENT_DIR)
    cities = _cities(cfg)
    page = client.page("2027 Cricket World Cup")
    w = page["wikitext"]
    heads = [(m.start(), m.group(1).strip()) for m in re.finditer(r"\n==+\s*([^=\n]+?)\s*==+", w)]
    fixtures = []
    for m in match_boxes._START.finditer(w):
        body = match_boxes._template_body(w, m.start())
        f = {}
        for line in body.split("\n")[1:]:
            fm = re.match(r"^\|\s*([a-z0-9_]+)\s*=\s*(.*)$", line.strip())
            if fm:
                f[fm.group(1)] = fm.group(2).strip()
        sec = [h for p, h in heads if p < m.start()][-1]
        no = re.search(r"Match (\d+)", f.get("round", ""))
        d = _START_DATE.search(f.get("date", ""))
        rid = re.search(r"match/(\d+)\.html", f.get("report", ""))
        venue = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", f.get("venue", "")).strip()
        tm = re.search(r"(\d{1,2}:\d{2})", f.get("time", ""))
        stage = {"Super Series": "super_series", "Group A": "group", "Group B": "group",
                 "Super 7": "super7", "Semi-finals": "semi", "Final": "final"}.get(sec, sec)
        fixtures.append({
            "match_no": int(no.group(1)) if no else None, "stage": stage,
            "group": sec[-1] if sec.startswith("Group") else ("S7" if stage == "super7" else ""),
            "date": "%s-%02d-%02d" % (d.group(1), int(d.group(2)), int(d.group(3))) if d else None,
            "slot1": _slot_2027(f.get("team1", ""), codes),
            "slot2": _slot_2027(f.get("team2", ""), codes),
            "venue": venue, "city": _city(venue), "venue_country": cities.get(_city(venue)),
            "match_key": rid.group(1) if rid else None, "time": tm.group(1) if tm else None,
            "daynight": "1" if f.get("daynight", "").strip().lower() in ("y", "yes") else "0"})
    # Knockouts and the Super Series have no match number in the box: number them in date order.
    nxt = max(f["match_no"] or 0 for f in fixtures)
    for f in sorted(fixtures, key=lambda f: f["date"]):
        if f["match_no"] is None:
            if f["stage"] == "super_series":
                continue
            nxt += 1
            f["match_no"] = nxt
    ss = sorted((f for f in fixtures if f["stage"] == "super_series"), key=lambda f: f["date"])
    for k, (f, pair) in enumerate(zip(ss, (("Q2", "Q3"), ("Q3", "Q4"), ("Q2", "Q4"))), start=1):
        f["match_no"], f["group"], f["slot1"], f["slot2"] = k, "SS", pair[0], pair[1]
    finals = [f for f in fixtures if f["stage"] == "final"]
    semis = sorted((f for f in fixtures if f["stage"] == "semi"), key=lambda f: f["date"])
    for f in finals:
        f["slot1"], f["slot2"] = "W%s" % semis[0]["match_no"], "W%s" % semis[1]["match_no"]
    return {"fixtures": fixtures, "revid": page["revid"]}


# -- validation ----------------------------------------------------------------------------------
def validate(fmt: Dict[str, object], fixtures: List[Dict[str, str]], known_teams: set) -> List[str]:
    errors = []
    nums = collections.Counter(f["match_no"] for f in fixtures)
    errors += ["match_no %s used %d times" % (k, n) for k, n in nums.items() if n > 1]
    teams = set(fmt["teams"])
    for t in teams:
        if t not in known_teams:
            errors.append("team %r is not a cricstat men's international team" % t)
    for f in fixtures:
        for s in (f["slot1"], f["slot2"]):
            if s not in teams and not _SLOT.match(s):
                errors.append("match %s: slot %r is neither a team nor a placeholder"
                              % (f["match_no"], s))
        if not f["venue_country"]:
            errors.append("match %s: no venue country (%s)" % (f["match_no"], f["venue"]))
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", f["date"] or ""):
            errors.append("match %s: bad date %r" % (f["match_no"], f["date"]))
    for st in fmt["stages"]:
        if st["kind"] != "round_robin":
            continue
        for g, members in st.get("groups", {}).items():
            pairs = collections.Counter(frozenset((f["slot1"], f["slot2"])) for f in fixtures
                                        if f["stage"] == st["id"] and f["group"] == g)
            want = {frozenset((a, b)) for i, a in enumerate(members) for b in members[i + 1:]}
            if set(pairs) != want or any(n != 1 for n in pairs.values()):
                errors.append("stage %s group %s: fixtures are not a single round robin of %s"
                              % (st["id"], g, members))
    return errors


def load(cfg, tid: str, known_teams: set) -> Tuple[Dict[str, object], List[Dict[str, str]]]:
    fmt = tournament_store.read_format(cfg.TOURNAMENTS_DIR, tid)
    fixtures = tournament_store.read_fixtures(cfg.TOURNAMENTS_DIR, tid)
    errors = validate(fmt, fixtures, known_teams | {"Afghanistan"})
    if errors:
        raise DataCheckError("tournament %s failed %d check(s): %s"
                             % (tid, len(errors), "; ".join(errors[:10])))
    return fmt, fixtures
