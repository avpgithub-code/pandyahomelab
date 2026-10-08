"""How far a rating can move before the tournament: the simulator's sigma (P1 plan §2.2).

A rating is a point estimate. A forecast made a year before a tournament has to allow for the team
being better or worse by then, and one made on the eve much less. sigma(days) is measured, not
chosen: for every Full Member and every month since 2007, the change in its Elo rating over the
next `days`, and the standard deviation of those changes. A random walk gives sigma ~ sqrt(days),
so sigma(days) = sqrt(a * days) is fitted by least squares on the measured points.
"""
import bisect
import datetime
import math
from typing import Dict, List, Tuple

from application_logic.models import elo

HORIZONS = (30, 60, 90, 180, 270, 365, 540)


def _ord(iso: str) -> int:
    return datetime.date.fromisoformat(iso).toordinal()


def measure(c: elo.Compiled, p: elo.EloParams, full_members: Dict[str, str],
            start: str = "2007-01-01", until: str = "9999-12-31") -> Dict[int, Tuple[float, int]]:
    """horizon days -> (SD of rating change, number of samples), Full Members only, using ratings
    from matches before `until`."""
    _, _, hist = elo.run(c, p, until=until, keep_history=True)
    series: Dict[int, Tuple[List[int], List[float]]] = {}
    for _key, date, team, rating in hist:
        days, vals = series.setdefault(team, ([], []))
        days.append(_ord(date))
        vals.append(rating)

    def at(team: int, day: int):
        days, vals = series[team]
        i = bisect.bisect_right(days, day) - 1
        return vals[i] if i >= 0 else None

    last = _ord(min(until, max(m.date for m in c.matches)))
    out = {}
    for hz in HORIZONS:
        diffs = []
        for t, name in enumerate(c.teams):
            if name not in full_members or t not in series:
                continue
            d = _ord(max(start, full_members[name]))
            while d + hz <= last:
                a, b = at(t, d), at(t, d + hz)
                if a is not None and b is not None:
                    diffs.append(b - a)
                d += 30
        if len(diffs) > 30:
            mean = sum(diffs) / len(diffs)
            out[hz] = (math.sqrt(sum((x - mean) ** 2 for x in diffs) / (len(diffs) - 1)),
                       len(diffs))
    return out


def fit(points: Dict[int, Tuple[float, int]]) -> float:
    """a in sigma(days) = sqrt(a * days), least squares on variance."""
    num = sum(hz * sd * sd for hz, (sd, _) in points.items())
    den = sum(hz * hz for hz in points)
    return num / den if den else 0.0


def sigma(a: float, days: float) -> float:
    return math.sqrt(max(a * days, 0.0))
