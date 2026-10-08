"""Baselines Elo has to beat (P1 plan §3.2).

coin      P(team1) = 0.5.
win_rate  our own "ranking-based" baseline (ICC rankings aren't used: ICC terms): each team's win
          share over the previous 730 days, (wins + ties/2 + 1) / (matches + 2), and the home flag,
          in a logistic model  logit P = b1 * (logit wr1 - logit wr2) + b2 * h  (no intercept: team
          order carries no information). Fitted only on matches before the year it predicts.
"""
import bisect
import datetime
import math
from typing import Dict, List, Tuple

from application_logic.models import metrics
from application_logic.models.elo import Compiled

WINDOW_DAYS = 730


def _ord(iso: str) -> int:
    return datetime.date(int(iso[:4]), int(iso[5:7]), int(iso[8:10])).toordinal()


def win_rate_features(c: Compiled) -> Dict[int, Tuple[float, int]]:
    """match index → (logit wr1 - logit wr2, h), using each team's results before the match."""
    past: Dict[int, List[Tuple[int, float]]] = {}       # team → [(day, score)] in date order
    feats: Dict[int, Tuple[float, int]] = {}

    def rate(team: int, day: int) -> float:
        hist = past.get(team, [])
        days = [d for d, _ in hist]
        lo = bisect.bisect_left(days, day - WINDOW_DAYS)
        hi = bisect.bisect_left(days, day)
        window = hist[lo:hi]
        return (sum(s for _, s in window) + 1.0) / (len(window) + 2.0)

    for i, m in enumerate(c.matches):
        if m.s1 is None:
            continue
        day = _ord(m.date)
        r1, r2 = rate(m.t1, day), rate(m.t2, day)
        feats[i] = (math.log(r1 / (1 - r1)) - math.log(r2 / (1 - r2)), m.h)
        past.setdefault(m.t1, []).append((day, m.s1))
        past.setdefault(m.t2, []).append((day, 1.0 - m.s1))
    return feats


def fit_win_rate(c: Compiled, feats, train_idx: List[int]) -> List[float]:
    xs = [[feats[i][0], float(feats[i][1])] for i in train_idx]
    ys = [c.matches[i].s1 for i in train_idx]
    return metrics.logistic_fit(xs, ys)


def predict_win_rate(w: List[float], feat: Tuple[float, int]) -> float:
    z = w[0] * feat[0] + w[1] * feat[1]
    return 1.0 / (1.0 + math.exp(-z))
