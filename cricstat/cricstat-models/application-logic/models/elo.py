"""Elo team ratings for men's ODIs (P1 plan §2.2). One rule for every team, no hand adjustments.

    E1 = 1 / (1 + 10 ** (-(R1 - R2 + H * h) / 400))     h = +1 team1 at home, -1 team2 at home, 0
    R1 += K * m * (S1 - E1);  R2 -= the same    S = 1 win, 0 loss, 0.5 tie (also when a super
                                                over decided it); no result: no change
Optional parts, kept only if they lower log loss on data before the test period:
    m      margin multiplier ln(1 + 10u) / ln 6 (u = runs/150 or wickets/10, capped at 1; m = 1 at
           u = 0.5) times 538's autocorrelation correction 2.2 / (0.001 * dR_winner + 2.2)
    r      each 1 January every team moves r of the way back to the base rating for its ICC status
           on that day (1500 Full Member, 1500 - delta Associate): a team promoted to Full Member
           (Ireland, Afghanistan in 2017) isn't pulled back toward its old associate start
    delta  starting rating 1500 for a Full Member at its first match in the data, 1500 - delta for
           an Associate (ICC status on that date, ratings/icc_full_members.csv)
Every prediction is made with the ratings as they stood before the match (one step ahead).
"""
import math
from typing import Dict, List, NamedTuple, Optional, Tuple

BASE = 1500.0


class EloParams(NamedTuple):
    k: float = 32.0
    home: float = 60.0
    margin: bool = False
    regress: float = 0.0
    delta: float = 0.0

    def as_dict(self) -> Dict[str, object]:
        return dict(self._asdict())


class Match(NamedTuple):
    key: str
    date: str
    year: int
    t1: int
    t2: int
    h: int                 # +1 team1 at home, -1 team2 at home, 0 neutral
    s1: Optional[float]    # 1 / 0 / 0.5; None = no result (no update, no prediction scored)
    u: Optional[float]     # normalised winning margin in (0, 1]; None for ties / no margin
    source: str


class Compiled(NamedTuple):
    matches: List[Match]
    teams: List[str]
    associate_at_start: List[bool]
    full_from: List[Optional[str]]      # date each team became a Full Member (None = associate)


def compile_matches(rows: List[Dict[str, object]], full_members: Dict[str, str]) -> Compiled:
    """rows from data_service.load_matches (oldest first) → compact tuples + team index.
    full_members: team → ISO date it became a Full Member."""
    teams: List[str] = []
    index: Dict[str, int] = {}
    first: Dict[str, str] = {}
    out: List[Match] = []
    for r in rows:
        if not r["has_play"]:
            continue
        for t in (r["team1"], r["team2"]):
            if t not in index:
                index[t] = len(teams)
                teams.append(t)
                first[t] = r["start_date"]
        h = 1 if r["home"] == r["team1"] else -1 if r["home"] == r["team2"] else 0
        s1: Optional[float]
        if r["result"] == "win":
            s1 = 1.0 if r["winner"] == r["team1"] else 0.0
        elif r["result"] == "tie":
            s1 = 0.5
        else:
            s1 = None
        u = None
        if r["result"] == "win":
            if r.get("margin_runs"):
                u = min(float(r["margin_runs"]) / 150.0, 1.0)
            elif r.get("margin_wickets"):
                u = min(float(r["margin_wickets"]) / 10.0, 1.0)
        out.append(Match(str(r["match_key"]), r["start_date"], int(r["start_date"][:4]),
                         index[r["team1"]], index[r["team2"]], h, s1, u, r["source"]))
    assoc = [not (t in full_members and full_members[t] <= first[t]) for t in teams]
    return Compiled(out, teams, assoc, [full_members.get(t) for t in teams])


_LN6 = math.log(6.0)


def run(c: Compiled, p: EloParams, until: Optional[str] = None, keep_history: bool = False
        ) -> Tuple[List[Tuple[int, float]], List[float], List[Tuple[str, str, int, float]]]:
    """Replay the matches. Returns (predictions, final ratings, history).
    predictions: (match index, P(team1 wins)) for every match with a result;
    history (if asked): (match key, date, team index, rating after the match).
    `until`: stop before this ISO date (ratings 'on the eve' of a tournament)."""
    start = [BASE - (p.delta if a else 0.0) for a in c.associate_at_start]
    rating = list(start)
    preds: List[Tuple[int, float]] = []
    hist: List[Tuple[str, str, int, float]] = []
    year = None
    k, home, regress = p.k, p.home, p.regress
    for i, m in enumerate(c.matches):
        if until is not None and m.date >= until:
            break
        if m.year != year:
            if year is not None and regress:
                jan1 = "%04d-01-01" % m.year
                target = [BASE if (f is not None and f <= jan1) else BASE - p.delta
                          for f in c.full_from]
                rating = [r - regress * (r - t) for r, t in zip(rating, target)]
            year = m.year
        d = rating[m.t1] - rating[m.t2] + home * m.h
        e1 = 1.0 / (1.0 + 10.0 ** (-d / 400.0))
        if m.s1 is None:
            continue
        preds.append((i, e1))
        mult = 1.0
        if p.margin and m.u is not None:
            dr_winner = d if m.s1 == 1.0 else -d
            mult = (math.log(1.0 + 10.0 * m.u) / _LN6) * (2.2 / (0.001 * dr_winner + 2.2))
        change = k * mult * (m.s1 - e1)
        rating[m.t1] += change
        rating[m.t2] -= change
        if keep_history:
            hist.append((m.key, m.date, m.t1, rating[m.t1]))
            hist.append((m.key, m.date, m.t2, rating[m.t2]))
    return preds, rating, hist


def probability(r1: float, r2: float, home: float, h: int) -> float:
    return 1.0 / (1.0 + 10.0 ** (-(r1 - r2 + home * h) / 400.0))
