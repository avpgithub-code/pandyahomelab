# admin-portal

Admin dashboard for pandyaHomeLab visitor analytics, plus the public feedback API
and page-view beacon. FastAPI + Jinja2, one container on `ml-network` (172.20.0.31),
data in the `analytics` schema of `ml-postgres`.

## Routes

| Route | Access | What |
|---|---|---|
| `/admin/?days=N` | Basic Auth | Dashboard (7d / 30d / 90d / 1y) |
| `/admin/feedback?page=/nlp/ewt-hmm/` | Basic Auth | Feedback by model: comments + likes with country / device / arrival source, "🏠 you" tag, hide / unhide. `page` is optional |
| `/feedback/likes`, `/feedback/comments` | public | Like + comment API used by `website/feedback-widget.js` |
| `/feedback/pv` | public | Page-view / engagement beacon from the same widget |
| `/admin/cricket` | Basic Auth | cricstat: scheduled jobs (CD pull, daily, weekly register, monthly), recent builds, data at a glance, golden summary |
| `/admin/cricket/golden` | Basic Auth | Golden-figure review: our figures vs references; **Verify References** (Wikipedia suggestions), accept/explain, export CSV |
| `/health` | public | Docker healthcheck |

Nginx keeps `/admin/*` and `/feedback/*` out of the JSON access log, so they never
count as visits.

## Dashboard

- **Real visitors** (top half) — from `analytics.page_views` / `page_events`, filled by the
  beacon. A page view counts when the page's JS ran, the user agent isn't a bot, it isn't
  from the owner's home IP, and the visitor interacted or stayed active ≥ 10 s. Panels:
  summary cards, daily chart, pages, demo actions, visit paths, countries, sources,
  visit length, devices.
- **🏠 Home IP (you)** — the owner's own visits, kept out of every number above.
- **Raw server log** (bottom) — `analytics.visitor_events` from the analytics-ingester
  (every nginx request, mostly scanners). Context only.

## Background jobs (in the app process)

| Job | File | Schedule | What |
|---|---|---|---|
| Home IP | `home_ip.py` | every 10 min | Resolves `HOME_IP_HOST` (DDNS name) and stores its salted hash in `analytics.home_ips` |
| Retention | `retention.py` | daily | Deletes `page_views`, `page_events`, `visitor_events` older than 13 months; strips the IP hash from likes/comments older than 13 months. Matches the public `/privacy/` page |

| cricstat golden check | `cricstat/runner.py` | weekly (checked hourly) | Recomputes golden statuses against cricstat-api; summary in `cricstat.golden_run`, shown in the weekly report |

Tables are created on startup by `schema.py` and `cricstat/store.py` (idempotent).

## cricstat section (P0.3b)

- Data: cricstat-api's internal `/v1/admin/{jobs,overview,golden}` over cricstat-network (the container
  joins it at 172.25.0.31; `CRICSTAT_API_URL`). No cricstat files are mounted here.
- Golden references, explanations and Wikipedia suggestions live in Postgres schema `cricstat`
  (`golden_reference`, `golden_suggestion`, `golden_run`). "Export CSV" gives the same columns as
  `cricstat/docs/validation/golden-figures.csv`; commit it to keep a record in the repo.
- Verify References: manual, one run at a time; Wikidata (P2697 = Cricinfo id) → English Wikipedia article →
  "Infobox cricketer" Test/ODI/T20I columns. Suggestions only; never ESPNcricinfo.
- POSTs under `/admin/cricket` refuse cross-site requests (Origin/Referer must match the host).
- Tests: `python3 -m pytest tests -q` (pure parts, no network or database).

## Weekly report

```sh
sudo docker exec admin-portal python -m app.weekly_report      # last 7 days
sudo docker exec admin-portal python -m app.weekly_report 30   # any window
```

Plain text, meant for a DSM Task Scheduler job with "Send run details by email".

## Environment

Set in `deployment/ml/.env` (gitignored), passed by `deployment/ml/docker-compose.dev.yml`.

| Var | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL DSN (same database as the ingester) |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Basic Auth for `/admin/` |
| `ANALYTICS_IP_SALT` | Salt for IP hashes — must match the analytics-ingester |
| `HOME_IP_HOST` | DDNS name of the owner's home connection; empty turns the Home IP split off |

## Build and deploy

The code is copied into the image, so every change needs a rebuild:

```sh
cd deployment/ml
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml build admin-portal
sudo docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --no-deps admin-portal
```

Use both compose files; the dev file alone fails with "undefined network ml-network".

## Layout

```
ml/admin-portal/
├── app/
│   ├── main.py               ← FastAPI factory, startup: schema + background jobs
│   ├── auth.py               ← HTTP Basic (constant-time compare)
│   ├── db.py                 ← psycopg2 helper, RealDictCursor
│   ├── schema.py             ← feedback, page_views, page_events, home_ips tables
│   ├── routes.py             ← /admin/ dashboard + moderation
│   ├── queries.py            ← raw server-log SQL (visitor_events)
│   ├── engagement_queries.py ← real-visitor + Home IP SQL, beacon writes
│   ├── beacon_routes.py      ← POST /feedback/pv
│   ├── feedback_routes.py    ← likes + comments API
│   ├── feedback_queries.py   ← feedback SQL
│   ├── bot_filter.py         ← UA bot patterns (keep in sync with analytics-ingester)
│   ├── ip_hasher.py          ← salted SHA-256 of the visitor IP
│   ├── home_ip.py            ← Home IP resolver job
│   ├── retention.py          ← 13-month retention job
│   ├── weekly_report.py      ← plain-text weekly summary
│   └── templates/            ← dashboard.html, moderation.html
└── docker/Dockerfile
```

## Auth security notes

- `secrets.compare_digest` for credential comparison (prevents timing attacks)
- Credentials live in `.env` (gitignored)
- HTTPS terminates at Cloudflare; the container only sees traffic from pandya-nginx
- For stronger auth later: Cloudflare Access in front (SSO), or bcrypt-hashed passwords
