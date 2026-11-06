"""The dashboard's reporting window: whole UTC calendar days, including today.

"30d" means today plus the 29 days before it, starting at 00:00 UTC. The window
therefore moves once a day at midnight UTC, not continuously, and the first day
on the chart is always a complete day. SQL takes the start as
date_trunc('day', NOW()) - win_param(days); the database session runs in UTC.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def win_param(days: int) -> str:
    """Interval back from today's midnight (today itself is one of the days)."""
    return f"{days - 1} days"


def window_start(days: int, today: date) -> date:
    return today - timedelta(days=days - 1)


def day_label(day: date) -> str:
    return f"{day:%b} {day.day}, {day.year}"


def window_label(start: date, end: date) -> str:
    """'Oct 8 – Nov 6, 2026', with the start year only when it differs."""
    first = f"{start:%b} {start.day}"
    if start.year != end.year:
        first += f", {start.year}"
    return f"{first} – {day_label(end)}"


def fill_days(rows: Iterable[Dict], start: Optional[date], end: date,
              keys: Iterable[str]) -> List[Dict]:
    """One row per day from start to end, oldest first; missing days are zeros."""
    if start is None:
        return []
    by_day = {r["day"]: r for r in rows}
    keys = list(keys)
    out = []
    for n in range((end - start).days + 1):
        day = start + timedelta(days=n)
        row = by_day.get(day, {})
        out.append({"day": day, **{k: int(row.get(k) or 0) for k in keys}})
    return out
