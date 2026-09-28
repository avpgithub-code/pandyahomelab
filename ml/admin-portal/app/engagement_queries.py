"""SQL for the page-view beacon (writes) and the "real visitors" dashboard (reads).

A page view counts as HUMAN when the browser ran our JS, the UA isn't a known bot,
it didn't come from the owner's home IP, and the visitor either interacted
(scroll/click/key/touch) or kept the tab visible and active for at least 10 seconds.
Everything on the dashboard's top half uses it. Home-IP visits are reported
separately (HOME_* queries).
"""
from typing import Dict, List

from app.db import get_cursor

HOME = "ip_hash IN (SELECT ip_hash FROM analytics.home_ips)"
HUMAN = f"NOT is_bot AND NOT {HOME} AND (interacted OR engaged_ms >= 10000)"
OWN_HOST = "(referrer_domain = 'pandyahomelab.com' OR referrer_domain LIKE '%%.pandyahomelab.com')"


# ─────────────────────────── Beacon writes ───────────────────────────

INSERT_SQL = """
INSERT INTO analytics.page_views
    (pv_id, visit_id, ip_hash, country, page_id, referrer_domain,
     utm_source, utm_medium, utm_campaign, device, lang, user_agent, is_bot)
VALUES
    (%(pv_id)s, %(visit_id)s, %(ip_hash)s, %(country)s, %(page_id)s, %(referrer_domain)s,
     %(utm_source)s, %(utm_medium)s, %(utm_campaign)s, %(device)s, %(lang)s, %(user_agent)s, %(is_bot)s)
ON CONFLICT (pv_id) DO NOTHING
"""

# Counters only move forward, and only the IP that started the page view can update it.
UPDATE_SQL = """
UPDATE analytics.page_views SET
    engaged_ms     = GREATEST(engaged_ms, %(engaged_ms)s),
    max_scroll_pct = GREATEST(max_scroll_pct, %(max_scroll_pct)s),
    interactions   = GREATEST(interactions, %(interactions)s),
    interacted     = interacted OR %(interactions)s > 0,
    last_seen_at   = NOW()
WHERE pv_id   = %(pv_id)s
  AND ip_hash = %(ip_hash)s
  AND started_at > NOW() - INTERVAL '6 hours'
"""

# page_id / visit_id come from the page view itself, so an event can only attach to
# a page view this IP started. Capped at 300 events per page view.
EVENT_INSERT_SQL = """
INSERT INTO analytics.page_events (pv_id, visit_id, ip_hash, page_id, name)
SELECT pv_id, visit_id, ip_hash, page_id, %(name)s
FROM analytics.page_views
WHERE pv_id   = %(pv_id)s
  AND ip_hash = %(ip_hash)s
  AND started_at > NOW() - INTERVAL '6 hours'
  AND (SELECT count(*) FROM analytics.page_events WHERE pv_id = %(pv_id)s) < 300
"""

RECENT_STARTS_SQL = """
SELECT count(*) AS n FROM analytics.page_views
WHERE ip_hash = %s AND started_at > NOW() - INTERVAL '10 minutes'
"""


def insert_page_view(row: Dict) -> None:
    with get_cursor() as cur:
        cur.execute(INSERT_SQL, row)
        cur.connection.commit()


def update_page_view(pv_id: str, ip_hash: str, engaged_ms: int,
                     max_scroll_pct: int, interactions: int) -> None:
    with get_cursor() as cur:
        cur.execute(UPDATE_SQL, {
            "pv_id": pv_id, "ip_hash": ip_hash, "engaged_ms": engaged_ms,
            "max_scroll_pct": max_scroll_pct, "interactions": interactions,
        })
        cur.connection.commit()


def insert_page_event(pv_id: str, ip_hash: str, name: str) -> None:
    with get_cursor() as cur:
        cur.execute(EVENT_INSERT_SQL, {"pv_id": pv_id, "ip_hash": ip_hash, "name": name})
        cur.connection.commit()


def count_recent_starts(ip_hash: str) -> int:
    with get_cursor() as cur:
        cur.execute(RECENT_STARTS_SQL, (ip_hash,))
        return int(cur.fetchone()["n"])


# ─────────────────────────── Dashboard reads ─────────────────────────

SUMMARY_SQL = f"""
WITH all_pv AS (
    SELECT * FROM analytics.page_views
    WHERE NOT is_bot AND NOT {HOME} AND started_at >= NOW() - %(win)s::interval
),
h AS (SELECT * FROM all_pv WHERE {HUMAN}),
v AS (
    SELECT visit_id, count(*) AS pages, sum(engaged_ms) AS engaged_ms
    FROM h GROUP BY visit_id
),
days_per_ip AS (
    SELECT ip_hash, count(DISTINCT started_at::date) AS d FROM h GROUP BY ip_hash
)
SELECT
    (SELECT count(*) FROM all_pv)                                       AS js_page_views,
    (SELECT count(*) FROM h)                                            AS page_views,
    (SELECT count(DISTINCT ip_hash) FROM h)                             AS visitors,
    (SELECT count(*) FROM v)                                            AS visits,
    (SELECT round(avg(engaged_ms) / 1000.0) FROM v)                     AS avg_visit_s,
    (SELECT round(avg(pages)::numeric, 1) FROM v)                       AS pages_per_visit,
    (SELECT round(100.0 * count(*) FILTER (WHERE pages = 1 AND engaged_ms < 30000)
                 / NULLIF(count(*), 0)) FROM v)                         AS bounce_pct,
    (SELECT count(*) FROM days_per_ip WHERE d > 1)                      AS returning_visitors,
    (SELECT count(DISTINCT h.ip_hash) FROM h
       JOIN analytics.page_events e ON e.pv_id = h.pv_id
      WHERE e.name LIKE 'run:%%')                                       AS demo_users
"""

DAILY_SQL = f"""
SELECT
    started_at::date                                   AS day,
    count(DISTINCT ip_hash)                            AS visitors,
    count(DISTINCT visit_id)                           AS visits,
    count(*)                                           AS page_views,
    round(sum(engaged_ms) / 1000.0 / NULLIF(count(DISTINCT visit_id), 0)) AS avg_visit_s
FROM analytics.page_views
WHERE {HUMAN} AND started_at >= NOW() - %(win)s::interval
GROUP BY 1
ORDER BY 1 DESC
"""

PAGES_SQL = f"""
WITH h AS (
    SELECT * FROM analytics.page_views
    WHERE {HUMAN} AND started_at >= NOW() - %(win)s::interval
),
runs AS (
    SELECT pv_id, count(*) AS n FROM analytics.page_events
    WHERE name LIKE 'run:%%' AND pv_id IN (SELECT pv_id FROM h)
    GROUP BY pv_id
)
SELECT
    h.page_id,
    coalesce(sum(runs.n), 0)                                        AS runs,
    round(100.0 * count(runs.pv_id) / count(*))                     AS ran_pct,
    count(*)                                                        AS views,
    count(DISTINCT h.ip_hash)                                       AS visitors,
    round(avg(h.engaged_ms) / 1000.0)                               AS avg_s,
    round((percentile_cont(0.5) WITHIN GROUP (ORDER BY h.engaged_ms) / 1000.0)::numeric) AS median_s,
    round(avg(h.max_scroll_pct))                                    AS avg_scroll,
    round(100.0 * count(*) FILTER (WHERE h.max_scroll_pct >= 75) / count(*)) AS read_pct,
    (SELECT count(*) FROM analytics.feedback_likes l
      WHERE l.page_id = h.page_id AND l.created_at >= NOW() - %(win)s::interval
        AND NOT l.{HOME}) AS likes,
    (SELECT count(*) FROM analytics.feedback_comments c
      WHERE c.page_id = h.page_id AND c.created_at >= NOW() - %(win)s::interval
        AND NOT c.{HOME}) AS comments
FROM h
LEFT JOIN runs ON runs.pv_id = h.pv_id
GROUP BY h.page_id
ORDER BY views DESC
LIMIT %(limit)s
"""

# Source of a visit = its first (landing) page view.
SOURCES_SQL = f"""
WITH landing AS (
    SELECT DISTINCT ON (visit_id) *
    FROM analytics.page_views
    WHERE {HUMAN} AND started_at >= NOW() - %(win)s::interval
    ORDER BY visit_id, started_at
)
SELECT
    CASE
        WHEN utm_source IS NOT NULL THEN utm_source || ' (utm)'
        WHEN referrer_domain IS NULL THEN '(direct)'
        WHEN {OWN_HOST} THEN '(internal / new tab)'
        ELSE referrer_domain
    END                                                AS source,
    count(*)                                           AS visits,
    count(DISTINCT ip_hash)                            AS visitors
FROM landing
GROUP BY 1
ORDER BY visits DESC
LIMIT %(limit)s
"""

COUNTRIES_SQL = f"""
SELECT country, count(DISTINCT ip_hash) AS visitors, count(DISTINCT visit_id) AS visits
FROM analytics.page_views
WHERE {HUMAN} AND country IS NOT NULL AND started_at >= NOW() - %(win)s::interval
GROUP BY country
ORDER BY visitors DESC
LIMIT %(limit)s
"""

DEVICES_SQL = f"""
SELECT coalesce(device, 'unknown') AS device, count(DISTINCT visit_id) AS visits
FROM analytics.page_views
WHERE {HUMAN} AND started_at >= NOW() - %(win)s::interval
GROUP BY 1
ORDER BY visits DESC
"""

# How long whole visits last — the clearest "how interested were they" view.
ENGAGEMENT_BUCKETS_SQL = f"""
WITH v AS (
    SELECT visit_id, sum(engaged_ms) AS ms
    FROM analytics.page_views
    WHERE {HUMAN} AND started_at >= NOW() - %(win)s::interval
    GROUP BY visit_id
)
SELECT bucket, count(*) AS visits FROM (
    SELECT CASE
        WHEN ms <  30000 THEN 1
        WHEN ms < 120000 THEN 2
        WHEN ms < 300000 THEN 3
        WHEN ms < 900000 THEN 4
        ELSE 5
    END AS bucket FROM v
) b
GROUP BY bucket
ORDER BY bucket
"""
BUCKET_LABELS = {1: "< 30 s", 2: "30 s – 2 min", 3: "2 – 5 min", 4: "5 – 15 min", 5: "15 min +"}


# What people did on each page (demo runs, examples, About panel).
ACTIONS_SQL = f"""
SELECT e.page_id, e.name, count(*) AS times, count(DISTINCT e.ip_hash) AS visitors
FROM analytics.page_events e
WHERE e.created_at >= NOW() - %(win)s::interval
  AND e.pv_id IN (SELECT pv_id FROM analytics.page_views WHERE {HUMAN})
GROUP BY e.page_id, e.name
ORDER BY visitors DESC, times DESC
LIMIT %(limit)s
"""


# Visit journeys: the pages of each visit in order, repeats of the same page
# collapsed, first 5 steps shown. Grouped so identical journeys add up.
JOURNEYS_SQL = f"""
WITH h AS (
    SELECT visit_id, page_id, started_at, engaged_ms
    FROM analytics.page_views
    WHERE {HUMAN} AND started_at >= NOW() - %(win)s::interval
),
steps AS (
    SELECT *, lag(page_id) OVER (PARTITION BY visit_id ORDER BY started_at) AS prev
    FROM h
),
dedup AS (
    SELECT visit_id, page_id, started_at,
           row_number() OVER (PARTITION BY visit_id ORDER BY started_at) AS n,
           count(*)     OVER (PARTITION BY visit_id)                     AS total
    FROM steps
    WHERE prev IS DISTINCT FROM page_id
),
journeys AS (
    SELECT visit_id,
           string_agg(page_id, ' → ' ORDER BY started_at)
             || CASE WHEN max(total) > 5 THEN ' → …' ELSE '' END AS journey
    FROM dedup WHERE n <= 5
    GROUP BY visit_id
)
SELECT j.journey,
       count(*)                                        AS visits,
       round(avg(t.ms) / 1000.0)                       AS avg_s
FROM journeys j
JOIN (SELECT visit_id, sum(engaged_ms) AS ms FROM h GROUP BY visit_id) t USING (visit_id)
GROUP BY j.journey
ORDER BY visits DESC, avg_s DESC
LIMIT %(limit)s
"""

# Page → next page within a visit: which pages send people onward, and where.
NEXT_PAGE_SQL = f"""
WITH steps AS (
    SELECT visit_id, page_id,
           lead(page_id) OVER (PARTITION BY visit_id ORDER BY started_at) AS next_page
    FROM analytics.page_views
    WHERE {HUMAN} AND started_at >= NOW() - %(win)s::interval
)
SELECT page_id AS from_page,
       coalesce(next_page, '(left the site)')          AS to_page,
       count(*)                                        AS times
FROM steps
WHERE next_page IS DISTINCT FROM page_id
GROUP BY 1, 2
ORDER BY times DESC
LIMIT %(limit)s
"""


# The owner's own activity from the home IP — kept out of everything above.
HOME_SUMMARY_SQL = f"""
WITH pv AS (
    SELECT * FROM analytics.page_views
    WHERE {HOME} AND started_at >= NOW() - %(win)s::interval
)
SELECT
    (SELECT count(*) FROM pv)                                        AS page_views,
    (SELECT count(DISTINCT visit_id) FROM pv)                        AS visits,
    (SELECT round(sum(engaged_ms) / 1000.0) FROM pv)                 AS engaged_s,
    (SELECT count(*) FROM analytics.page_events e
      WHERE e.pv_id IN (SELECT pv_id FROM pv) AND e.name LIKE 'run:%%') AS demo_runs,
    (SELECT count(*) FROM analytics.feedback_likes
      WHERE {HOME} AND created_at >= NOW() - %(win)s::interval)      AS likes,
    (SELECT count(*) FROM analytics.feedback_comments
      WHERE {HOME} AND created_at >= NOW() - %(win)s::interval)      AS comments,
    (SELECT max(started_at) FROM pv)                                 AS last_seen,
    (SELECT count(*) FROM analytics.home_ips)                        AS known_ips
"""

HOME_PAGES_SQL = f"""
SELECT page_id, count(*) AS views, round(sum(engaged_ms) / 1000.0) AS engaged_s
FROM analytics.page_views
WHERE {HOME} AND started_at >= NOW() - %(win)s::interval
GROUP BY page_id
ORDER BY views DESC
LIMIT %(limit)s
"""


def _fetch(sql: str, days: int, limit: int = 10) -> List[Dict]:
    with get_cursor() as cur:
        cur.execute(sql, {"win": f"{days} days", "limit": limit})
        return [dict(r) for r in cur.fetchall()]


def fetch_engagement_summary(days: int) -> Dict:
    rows = _fetch(SUMMARY_SQL, days)
    return rows[0] if rows else {}


def fetch_engagement_daily(days: int) -> List[Dict]:
    return _fetch(DAILY_SQL, days)


def fetch_page_engagement(days: int, limit: int = 20) -> List[Dict]:
    return _fetch(PAGES_SQL, days, limit)


def fetch_visit_sources(days: int, limit: int = 10) -> List[Dict]:
    return _fetch(SOURCES_SQL, days, limit)


def fetch_human_countries(days: int, limit: int = 10) -> List[Dict]:
    return _fetch(COUNTRIES_SQL, days, limit)


def fetch_devices(days: int) -> List[Dict]:
    return _fetch(DEVICES_SQL, days)


def fetch_engagement_buckets(days: int) -> List[Dict]:
    counts = {r["bucket"]: int(r["visits"]) for r in _fetch(ENGAGEMENT_BUCKETS_SQL, days)}
    return [{"label": BUCKET_LABELS[b], "visits": counts.get(b, 0)} for b in sorted(BUCKET_LABELS)]


def fetch_page_actions(days: int, limit: int = 25) -> List[Dict]:
    return _fetch(ACTIONS_SQL, days, limit)


def fetch_journeys(days: int, limit: int = 10) -> List[Dict]:
    return _fetch(JOURNEYS_SQL, days, limit)


def fetch_next_pages(days: int, limit: int = 15) -> List[Dict]:
    return _fetch(NEXT_PAGE_SQL, days, limit)


def fetch_home_summary(days: int) -> Dict:
    rows = _fetch(HOME_SUMMARY_SQL, days)
    return rows[0] if rows else {}


def fetch_home_pages(days: int, limit: int = 10) -> List[Dict]:
    return _fetch(HOME_PAGES_SQL, days, limit)
