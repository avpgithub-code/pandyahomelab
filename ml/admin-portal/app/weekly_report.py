"""Weekly real-visitor summary, printed as plain text.

Run inside the container:
    docker exec admin-portal python -m app.weekly_report          # last 7 days
    docker exec admin-portal python -m app.weekly_report 30       # any window

Scheduled weekly from DSM Task Scheduler with "Send run details by email", so
DSM's existing Gmail notification setup delivers whatever this prints.
"""
import sys
from datetime import datetime, timezone

from app.db import get_cursor
from app.engagement_queries import (
    HOME,
    HUMAN,
    fetch_home_summary,
    fetch_engagement_summary,
    fetch_human_countries,
    fetch_journeys,
    fetch_page_actions,
    fetch_page_engagement,
    fetch_visit_sources,
)

PREVIOUS_SQL = f"""
SELECT count(DISTINCT ip_hash) AS visitors,
       count(DISTINCT visit_id) AS visits,
       count(*)                 AS page_views
FROM analytics.page_views
WHERE {HUMAN}
  AND started_at >= NOW() - 2 * %(win)s::interval
  AND started_at <  NOW() - %(win)s::interval
"""

COMMENTS_SQL = f"""
SELECT page_id, coalesce(name, 'anonymous') AS name, body, created_at, {HOME} AS from_home
FROM analytics.feedback_comments
WHERE NOT hidden AND created_at >= NOW() - %(win)s::interval
ORDER BY created_at DESC
LIMIT 10
"""

LIKES_SQL = f"""
SELECT count(*) AS n FROM analytics.feedback_likes
WHERE NOT {HOME} AND created_at >= NOW() - %(win)s::interval
"""


def _query(sql: str, days: int):
    with get_cursor() as cur:
        cur.execute(sql, {"win": f"{days} days"})
        return [dict(r) for r in cur.fetchall()]


def _dur(s) -> str:
    if s is None:
        return "—"
    s = int(s)
    return f"{s}s" if s < 60 else f"{s // 60}m {s % 60:02d}s"


def _change(now, before) -> str:
    now, before = int(now or 0), int(before or 0)
    if before == 0:
        return "(new)" if now else ""
    pct = round(100 * (now - before) / before)
    return f"({'+' if pct >= 0 else ''}{pct}% vs previous)"


def build_report(days: int = 7) -> str:
    s = fetch_engagement_summary(days)
    prev = _query(PREVIOUS_SQL, days)[0]
    likes = _query(LIKES_SQL, days)[0]["n"]
    out = []
    w = out.append

    w(f"pandyaHomeLab — real visitors, last {days} days")
    w(f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · https://pandyahomelab.com/admin/?days={days}")
    w("")
    w(f"  Visitors        {s.get('visitors') or 0:>6}  {_change(s.get('visitors'), prev['visitors'])}")
    w(f"  Visits          {s.get('visits') or 0:>6}  {_change(s.get('visits'), prev['visits'])}")
    w(f"  Page views      {s.get('page_views') or 0:>6}  {_change(s.get('page_views'), prev['page_views'])}")
    w(f"  Tried a demo    {s.get('demo_users') or 0:>6}")
    w(f"  Returning       {s.get('returning_visitors') or 0:>6}")
    w(f"  Avg visit time  {_dur(s.get('avg_visit_s')):>6}")
    w(f"  Pages / visit   {s.get('pages_per_visit') or '—':>6}")
    bounce = s.get("bounce_pct")
    w(f"  Bounce rate     {(str(int(bounce)) + '%') if bounce is not None else '—':>6}")
    w(f"  New likes       {likes:>6}")
    home = fetch_home_summary(days)
    if home.get("page_views"):
        w(f"  (Not counted: your home IP — {home['page_views']} page views in {home['visits']} visits)")

    pages = fetch_page_engagement(days, limit=10)
    if pages:
        w("")
        w("TOP PAGES               views  visitors  avg time  ran demo")
        for p in pages:
            w(f"  {p['page_id'][:22]:<22} {p['views']:>5}  {p['visitors']:>8}  {_dur(p['avg_s']):>8}  {int(p['ran_pct'] or 0):>7}%")

    actions = fetch_page_actions(days, limit=10)
    if actions:
        w("")
        w("WHAT PEOPLE DID")
        for a in actions:
            w(f"  {a['page_id']} · {a['name']} — {a['times']}× by {a['visitors']} visitor(s)")

    journeys = fetch_journeys(days, limit=5)
    if journeys:
        w("")
        w("TOP JOURNEYS")
        for j in journeys:
            w(f"  {j['visits']:>3}×  {j['journey']}  (avg {_dur(j['avg_s'])})")

    sources = fetch_visit_sources(days, limit=8)
    if sources:
        w("")
        w("SOURCES   " + " · ".join(f"{r['source']} {r['visits']}" for r in sources))

    countries = fetch_human_countries(days, limit=8)
    if countries:
        w("COUNTRIES " + " · ".join(f"{r['country']} {r['visitors']}" for r in countries))

    comments = _query(COMMENTS_SQL, days)
    if comments:
        w("")
        w("NEW COMMENTS")
        for c in comments:
            body = " ".join(c["body"].split())
            tag = " (home IP)" if c["from_home"] else ""
            w(f"  [{c['created_at']:%b %d}] {c['page_id']} — {c['name']}{tag}: {body[:200]}{'…' if len(body) > 200 else ''}")

    if not (s.get("visitors") or 0):
        w("")
        w("No real visitors recorded in this window.")

    try:                                     # cricstat jobs + golden check (P0.3b)
        from app.cricstat.runner import report_lines
        out.extend(report_lines())
    except Exception as e:                   # never lose the visitor report over cricstat
        w("")
        w(f"CRICSTAT section failed: {e}")
    return "\n".join(out)


if __name__ == "__main__":
    window = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print(build_report(window))
