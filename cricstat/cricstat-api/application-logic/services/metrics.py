"""Ratio formulas for groupings the F4 views can't express (years, phases, splits, team windows).

They mirror cricstat/sql/semantic_views.sql exactly (F4 R17/R19), and tests check that these
functions give the views' numbers for every scope. Undefined → None (shown as "—").
"""
from typing import Optional


def _div(a, b) -> Optional[float]:
    return None if not b or a is None else a / b


def batting_average(runs, outs) -> Optional[float]:
    """runs ÷ dismissals (retired hurt / not out are not dismissals)."""
    return _div(runs, outs)


def strike_rate(runs, balls_faced) -> Optional[float]:
    """runs × 100 ÷ balls faced (wides are not balls faced)."""
    return None if not balls_faced or runs is None else runs * 100.0 / balls_faced


def bowling_average(runs_conceded, wickets) -> Optional[float]:
    return _div(runs_conceded, wickets)


def economy(runs_conceded, legal_balls) -> Optional[float]:
    """runs conceded × 6 ÷ legal balls (per 6 legal balls in every format)."""
    return None if not legal_balls or runs_conceded is None else runs_conceded * 6.0 / legal_balls


def bowling_strike_rate(legal_balls, wickets) -> Optional[float]:
    return _div(legal_balls, wickets)


def win_pct(won, matches, no_result) -> Optional[float]:
    """won ÷ (matches − no results) × 100; ties and draws stay in the denominator."""
    played = (matches or 0) - (no_result or 0)
    return None if played <= 0 else (won or 0) * 100.0 / played


def overs_display(legal_balls) -> str:
    legal_balls = legal_balls or 0
    return "%d.%d" % (legal_balls // 6, legal_balls % 6)


# What each returned ratio means, for meta.metrics (F5 §2); wording from semantic_catalog.
DEFINITIONS = {
    "average": "Batting average = runs ÷ dismissals (retired hurt is not out).",
    "strike_rate": "Batting strike rate = runs × 100 ÷ balls faced (wides excluded).",
    "bowling_average": "Bowling average = runs conceded ÷ wickets.",
    "economy": "Economy = runs conceded × 6 ÷ legal balls; byes, leg-byes and penalty runs are not"
               " charged to the bowler; super overs excluded.",
    "bowling_strike_rate": "Bowling strike rate = legal balls ÷ wickets.",
    "win_pct": "Win % = won ÷ (matches − no results) × 100; ties and draws stay in the"
               " denominator.",
}
