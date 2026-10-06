"""Turn one parsed Cricsheet match into serving-DB facts. Pure: no SQL, no I/O.

Players are identified by their Cricsheet id (resolved per match through info.registry.people),
teams by name, venues by (name, city). The repository assigns the integer surrogate keys.

The cricket rules are NOT written here: format mapping, phases and the dismissal-kind flags arrive
in `Rules`, loaded from the reference tables (cricstat/sql/reference_data.sql). This module only
applies them as docs/F4-metric-dictionary.md describes (R1–R22).
"""
from typing import Dict, List, NamedTuple, Optional, Tuple

RESULTS = {"tie": "tie", "draw": "draw", "no result": "no_result"}


class Rules(NamedTuple):
    formats: Dict[Tuple[str, str, int], Tuple[str, str, str]]  # → (format_key, family, level)
    kinds: Dict[str, Tuple[int, int]]                          # kind → (credited, counts_as_out)
    phases: Dict[str, List[Tuple[str, int, int]]]              # family → [(phase, from, to)]


class MatchFacts:
    """Everything one match contributes to the serving DB, keyed by natural ids."""

    def __init__(self, match_id: str):
        self.match_id = match_id
        self.match: dict = {}
        self.players: Dict[str, str] = {}        # player_id → name as written in this match
        self.unresolved: List[str] = []          # names with no registry entry (a build check)
        self.problems: List[str] = []            # unmapped format / kind / outcome (a build check)
        self.match_players: List[tuple] = []     # (team, player_id, role)
        self.player_of_match: List[str] = []
        self.officials: List[tuple] = []         # (role, name)
        self.innings: List[dict] = []
        self.absent_hurt: List[tuple] = []       # (innings_no, player_id)
        self.powerplays: List[tuple] = []        # (innings_no, seq, from, to, type)
        self.miscounted: List[tuple] = []        # (innings_no, over_no, balls)
        self.deliveries: List[tuple] = []
        self.dismissals: List[tuple] = []
        self.fielders: List[tuple] = []
        self.reviews: List[tuple] = []
        self.replacements: List[tuple] = []
        self.batting: List[dict] = []            # atoms, one per player per innings
        self.bowling: List[dict] = []
        self.fielding: List[dict] = []
        self.phase_stats: List[dict] = []
        self.team_results: List[dict] = []
        self.n_deliveries = 0


def _int(v) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _parse_outcome(outcome: dict, facts: MatchFacts) -> dict:
    """outcome → result / winner / margins / method / decided_by (F3 §5, F4 R14)."""
    by = outcome.get("by") or {}
    res = {"result": None, "winner": None, "win_by_runs": _int(by.get("runs")),
           "win_by_wickets": _int(by.get("wickets")), "win_by_innings": _int(by.get("innings")),
           "method": outcome.get("method"), "decided_by": "play"}
    if outcome.get("winner"):
        res["result"], res["winner"] = "win", outcome["winner"]
    elif outcome.get("result") in RESULTS:
        res["result"] = RESULTS[outcome["result"]]
        if outcome.get("eliminator"):
            res["winner"], res["decided_by"] = outcome["eliminator"], "super_over"
        elif outcome.get("bowl_out"):
            res["winner"], res["decided_by"] = outcome["bowl_out"], "bowl_out"
    else:
        facts.problems.append("outcome shape %s" % sorted(outcome))
        res["result"] = "no_result"
    if res["method"] == "Awarded":
        res["decided_by"] = "award"
    return res


def build_facts(match_id: str, doc: dict, rules: Rules) -> MatchFacts:
    f = MatchFacts(match_id)
    info = doc["info"]
    registry = (info.get("registry") or {}).get("people") or {}

    def pid(name: Optional[str], quiet: bool = False) -> Optional[str]:
        """Resolve a name through this match's registry. quiet: a miss is expected (substitute
        fielders are often not in the registry, F3 §5) and is not reported as unresolved."""
        if not name:
            return None
        p = registry.get(name)
        if p is None:
            if not quiet and name not in f.unresolved:
                f.unresolved.append(name)
            return None
        f.players.setdefault(p, name)
        return p

    mt, tt = info.get("match_type"), info.get("team_type")
    bpo = info.get("balls_per_over", 6)
    fmt = rules.formats.get((mt, tt, bpo))
    if fmt is None:
        f.problems.append("unmapped format (%s, %s, %s)" % (mt, tt, bpo))
        fmt = (None, None, None)
    format_key, family, _level = fmt
    dates = sorted(d for d in info.get("dates", []) if isinstance(d, str))
    teams = list(info.get("teams") or [])
    event = info.get("event") or {}
    toss = info.get("toss") or {}
    venue = info.get("venue")
    out = _parse_outcome(info.get("outcome") or {}, f)
    has_deliveries = any(ov.get("deliveries") for inn in doc.get("innings", [])
                         for ov in inn.get("overs", []))
    f.match = dict(
        match_id=match_id, match_type=mt, team_type=tt, gender=info.get("gender"),
        balls_per_over=bpo, format_key=format_key, format_family=family,
        overs_limit=_int(info.get("overs")), match_type_number=_int(info.get("match_type_number")),
        event_name=event.get("name"), event_match_number=_int(event.get("match_number")),
        event_stage=event.get("stage"), event_group=(None if event.get("group") is None
                                                     else str(event.get("group"))),
        season=str(info.get("season", dates[0][:4] if dates else "")),
        start_date=dates[0] if dates else None, end_date=dates[-1] if dates else None,
        n_days=len(dates), venue=venue, city=info.get("city"),
        team1=teams[0] if teams else None, team2=teams[1] if len(teams) > 1 else None,
        toss_winner=toss.get("winner"), toss_decision=toss.get("decision"),
        has_deliveries=1 if has_deliveries else 0, **out)

    for team, names in (info.get("players") or {}).items():
        for name in names:
            p = pid(name)
            if p:
                f.match_players.append((team, p, "xi"))
    for team, name in (info.get("supersubs") or {}).items():
        p = pid(name)
        if p:
            f.match_players.append((team, p, "supersub"))
    for name in info.get("player_of_match") or []:
        p = pid(name)
        if p and p not in f.player_of_match:
            f.player_of_match.append(p)
    for role, names in (info.get("officials") or {}).items():
        for name in names:
            if (role, name) not in f.officials:
                f.officials.append((role, name))

    for no, inn in enumerate(doc.get("innings", []), start=1):
        _innings(f, no, inn, teams, family, bpo, rules, pid)

    if has_deliveries and f.match["team1"] and f.match["team2"]:
        for team, opp in ((f.match["team1"], f.match["team2"]),
                          (f.match["team2"], f.match["team1"])):
            r = f.match["result"]
            if r == "win":
                outcome = "won" if f.match["winner"] == team else "lost"
            else:
                outcome = {"tie": "tied", "draw": "drawn"}.get(r, "no_result")
            f.team_results.append(dict(team=team, opponent=opp, outcome=outcome,
                                       margin_runs=f.match["win_by_runs"],
                                       margin_wickets=f.match["win_by_wickets"]))
    return f


def _innings(f: MatchFacts, no: int, inn: dict, teams: list, family: Optional[str], bpo: int,
             rules: Rules, pid) -> None:
    team = inn.get("team")
    opp = next((t for t in teams if t != team), None)
    is_super = 1 if inn.get("super_over") else 0
    target = inn.get("target") or {}
    pens = inn.get("penalty_runs") or {}
    pen_pre, pen_post = pens.get("pre", 0) or 0, pens.get("post", 0) or 0
    for name in inn.get("absent_hurt") or []:
        p = pid(name)
        if p:
            f.absent_hurt.append((no, p))
    for seq, pp in enumerate(inn.get("powerplays") or [], start=1):
        f.powerplays.append((no, seq, str(pp.get("from")), str(pp.get("to")), pp.get("type")))
    miscounted = {}
    for over, detail in (inn.get("miscounted_overs") or {}).items():
        balls = int(detail.get("balls") if isinstance(detail, dict) else detail)  # "7" in the data
        miscounted[int(over)] = balls
        f.miscounted.append((no, int(over), balls))
    phase_of = {}
    for phase, lo, hi in rules.phases.get(family or "", []):
        for o in range(lo, hi + 1):
            phase_of[o] = phase

    bat: Dict[str, dict] = {}
    bowl: Dict[str, dict] = {}
    fld: Dict[str, dict] = {}
    ph: Dict[Tuple[str, str], dict] = {}
    total_runs = pen_pre + pen_post
    total_wkts = legal_total = 0

    def batter(p):
        if p not in bat:
            bat[p] = dict(player=p, batting_position=len(bat) + 1, runs=0, balls_faced=0, fours=0,
                          sixes=0, is_out=0, dismissal_kind=None)
        return bat[p]

    def bowler(p):
        if p not in bowl:
            bowl[p] = dict(player=p, legal_balls=0, runs_conceded=0, wickets=0, maidens=0,
                           wides=0, noballs=0, dots=0)
        return bowl[p]

    def fielder(p):
        if p not in fld:
            fld[p] = dict(player=p, catches=0, stumpings=0, run_outs=0, as_substitute=0)
        return fld[p]

    def phase_row(p, phase):
        key = (p, phase)
        if key not in ph:
            ph[key] = dict(player=p, phase=phase, bat_runs=0, bat_balls=0, bat_outs=0,
                           bowl_balls=0, bowl_runs=0, bowl_wkts=0)
        return ph[key]

    for ov in inn.get("overs", []):
        over_no = ov.get("over")
        over_bowlers = set()
        over_conceded = over_legal = 0
        phase = None if is_super else phase_of.get(over_no)
        for seq, d in enumerate(ov.get("deliveries", []), start=1):
            f.n_deliveries += 1
            runs = d.get("runs") or {}
            ex = d.get("extras") or {}
            rb, rex, rtot = runs.get("batter", 0), runs.get("extras", 0), runs.get("total", 0)
            wd, nb = ex.get("wides", 0), ex.get("noballs", 0)
            by, lb, pen = ex.get("byes", 0), ex.get("legbyes", 0), ex.get("penalty", 0)
            non_boundary = 1 if runs.get("non_boundary") else 0
            legal = 0 if (wd or nb) else 1
            b, ns, bw = pid(d.get("batter")), pid(d.get("non_striker")), pid(d.get("bowler"))
            wickets = d.get("wickets") or []
            total_runs += rtot
            legal_total += legal
            if b and ns and bw:
                f.deliveries.append((no, over_no, seq, d.get("actual_delivery"), b, ns, bw, rb, rex,
                                     rtot, non_boundary, wd, nb, by, lb, pen, legal, len(wickets)))
            conceded = rb + wd + nb                             # R4
            over_bowlers.add(bw)
            over_conceded += conceded
            over_legal += legal
            if b:                                               # R11: striker, then non-striker
                bi = batter(b)
                bi["runs"] += rb
                if not wd:                                      # R3
                    bi["balls_faced"] += 1
                if not non_boundary and rb in (4, 6):           # R10
                    bi["fours" if rb == 4 else "sixes"] += 1
            if ns:
                batter(ns)
            if bw:
                bo = bowler(bw)
                bo["legal_balls"] += legal                      # R5
                bo["runs_conceded"] += conceded
                bo["wides"] += 1 if wd else 0
                bo["noballs"] += 1 if nb else 0
                if legal and conceded == 0:                     # R8
                    bo["dots"] += 1
            if phase:
                if b:
                    pr = phase_row(b, phase)
                    pr["bat_runs"] += rb
                    pr["bat_balls"] += 0 if wd else 1
                if bw:
                    pr = phase_row(bw, phase)
                    pr["bowl_balls"] += legal
                    pr["bowl_runs"] += conceded
            for wseq, w in enumerate(wickets, start=1):
                kind = w.get("kind")
                if kind not in rules.kinds:
                    f.problems.append("unknown dismissal kind %r" % kind)
                credited, counts_out = rules.kinds.get(kind, (0, 1))
                out = pid(w.get("player_out"))
                if out:
                    f.dismissals.append((no, over_no, seq, wseq, out, kind, bw, credited,
                                         counts_out))
                    bi = batter(out)
                    if counts_out:                              # R1
                        bi["is_out"], bi["dismissal_kind"] = 1, kind
                        total_wkts += 1
                        if phase:
                            phase_row(out, phase)["bat_outs"] += 1
                    elif not bi["is_out"]:
                        bi["dismissal_kind"] = kind
                if credited and bw:                             # R2
                    bowler(bw)["wickets"] += 1
                    if phase:
                        phase_row(bw, phase)["bowl_wkts"] += 1
                for fseq, fe in enumerate(w.get("fielders") or [], start=1):
                    fname = fe.get("name")
                    sub = 1 if fe.get("substitute") else 0
                    fp = pid(fname, quiet=bool(sub))
                    f.fielders.append((no, over_no, seq, wseq, fseq, fp, fname or "", sub))
                    if is_super or not fp:
                        continue
                    if kind == "caught":                        # R12
                        if sub:
                            fielder(fp)["as_substitute"] += 1
                        else:
                            fielder(fp)["catches"] += 1
                    elif kind == "stumped" and not sub:
                        fielder(fp)["stumpings"] += 1
                    elif kind == "run out":
                        fielder(fp)["run_outs"] += 1
                if kind == "caught and bowled" and bw and not is_super:
                    fielder(bw)["catches"] += 1
            rv = d.get("review")
            if rv:
                f.reviews.append((no, over_no, seq, rv.get("by"), rv.get("umpire"),
                                  pid(rv.get("batter")) if rv.get("batter") else None,
                                  rv.get("decision"), 1 if rv.get("umpires_call") else 0,
                                  rv.get("type")))
            for rkind, items in (d.get("replacements") or {}).items():
                for r in items:
                    p_in = pid(r.get("in"))
                    p_out = pid(r.get("out"))
                    f.replacements.append((no, over_no, seq, rkind, r.get("team"), p_in, p_out,
                                           r.get("reason"), r.get("role")))
                    if rkind == "match" and p_in and r.get("team"):
                        f.match_players.append((r["team"], p_in, "replacement"))
        # R6: one bowler bowls the whole (complete) over and concedes 0; never in the Hundred.
        expected = miscounted.get(over_no, bpo)
        if (family != "hundred" and len(over_bowlers) == 1 and None not in over_bowlers
                and over_legal >= expected and over_conceded == 0):
            bowl[next(iter(over_bowlers))]["maidens"] += 1

    f.innings.append(dict(
        innings_no=no, team=team, opponent=opp, is_super_over=is_super,
        declared=1 if inn.get("declared") else 0, forfeited=1 if inn.get("forfeited") else 0,
        target_runs=_int(target.get("runs")), target_overs=target.get("overs"),
        penalty_runs_pre=pen_pre, penalty_runs_post=pen_post, total_runs=total_runs,
        total_wickets=total_wkts, legal_balls=legal_total))
    for row in bat.values():
        f.batting.append(dict(row, innings_no=no, team=team, opponent=opp, is_super_over=is_super))
    for row in bowl.values():
        f.bowling.append(dict(row, innings_no=no, team=opp, opponent=team, is_super_over=is_super))
    if not is_super:
        for row in fld.values():
            f.fielding.append(dict(row, innings_no=no))
        for row in ph.values():
            f.phase_stats.append(dict(row, innings_no=no))

