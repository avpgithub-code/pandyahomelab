"""Forecast quality measures (P1 plan §3.2). y is team1's score: 1 win, 0 loss, 0.5 tie."""
import math
from typing import Dict, List, Sequence, Tuple

EPS = 1e-12


def brier(p: Sequence[float], y: Sequence[float]) -> float:
    return sum((a - b) ** 2 for a, b in zip(p, y)) / len(p)


def log_loss(p: Sequence[float], y: Sequence[float]) -> float:
    total = 0.0
    for a, b in zip(p, y):
        a = min(max(a, EPS), 1 - EPS)
        total -= b * math.log(a) + (1 - b) * math.log(1 - a)
    return total / len(p)


def accuracy(p: Sequence[float], y: Sequence[float]) -> float:
    """Share of decided matches where the favourite won (ties and 50/50 calls left out)."""
    hits = [(a > 0.5) == (b == 1.0) for a, b in zip(p, y) if b != 0.5 and a != 0.5]
    return sum(hits) / len(hits) if hits else float("nan")


def reliability(p: Sequence[float], y: Sequence[float],
                edges=(0.5, 0.6, 0.7, 0.8, 0.9, 1.0001)) -> List[Dict[str, float]]:
    """The favourite's view: predicted vs observed win rate per bin, with counts."""
    rows = []
    fav = [(a, b) if a >= 0.5 else (1 - a, 1 - b) for a, b in zip(p, y)]
    for lo, hi in zip(edges, edges[1:]):
        sel = [(a, b) for a, b in fav if lo <= a < hi]
        if sel:
            rows.append({"bin": "%.1f-%.1f" % (lo, min(hi, 1.0)), "n": len(sel),
                         "predicted": sum(a for a, _ in sel) / len(sel),
                         "observed": sum(b for _, b in sel) / len(sel)})
    return rows


def logistic_fit(xs: List[List[float]], y: Sequence[float], l2: float = 1e-6,
                 iters: int = 50) -> List[float]:
    """Logistic regression by Newton's method (a handful of features, no dependency).
    y may be 0.5 for ties: the likelihood stays well defined."""
    n = len(xs[0])
    w = [0.0] * n
    for _ in range(iters):
        g = [0.0] * n
        hm = [[0.0] * n for _ in range(n)]
        for x, t in zip(xs, y):
            z = sum(a * b for a, b in zip(w, x))
            q = 1.0 / (1.0 + math.exp(-max(min(z, 35.0), -35.0)))
            for i in range(n):
                g[i] += (q - t) * x[i]
                for j in range(n):
                    hm[i][j] += q * (1 - q) * x[i] * x[j]
        for i in range(n):
            g[i] += l2 * w[i]
            hm[i][i] += l2
        step = _solve(hm, g)
        w = [a - b for a, b in zip(w, step)]
        if max(abs(s) for s in step) < 1e-9:
            break
    return w


def _solve(a: List[List[float]], b: List[float]) -> List[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        for r in range(n):
            if r != c and m[c][c]:
                f = m[r][c] / m[c][c]
                m[r] = [x - f * y for x, y in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] if m[i][i] else 0.0 for i in range(n)]


def calibration(p: Sequence[float], y: Sequence[float]) -> Tuple[float, float]:
    """(intercept, slope) of logit(P(y)) = a + b * logit(p). Perfect calibration: (0, 1);
    slope < 1 means overconfident, > 1 underconfident."""
    xs = []
    for a in p:
        a = min(max(a, 1e-6), 1 - 1e-6)
        xs.append([1.0, math.log(a / (1 - a))])
    a, b = logistic_fit(xs, list(y))
    return a, b


def summary(p: Sequence[float], y: Sequence[float]) -> Dict[str, object]:
    a, b = calibration(p, y)
    return {"n": len(p), "brier": brier(p, y), "log_loss": log_loss(p, y),
            "accuracy": accuracy(p, y), "calibration_intercept": a, "calibration_slope": b,
            "reliability": reliability(p, y)}
