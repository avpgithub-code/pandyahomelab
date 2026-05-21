# admin-portal

Admin-only dashboard for pandyaHomeLab visitor analytics. Reads from
`analytics.visitor_events` in `ml-postgres`, renders a server-side HTML page
behind HTTP Basic Auth.

## What's in Step 2.4 (this version)

- HTTP Basic Auth (credentials from `ADMIN_USERNAME` + `ADMIN_PASSWORD` env vars)
- Single dashboard page: `/`
  - **Summary cards** — total events, real visits, bot visits, unique visitors, unique paths
  - **Daily breakdown** table — events / real / unique / bots per day
  - **Top 5 paths** table — real visitors only
  - **Window selector** — 7d / 30d / 90d / 1y via `?days=N` query parameter
- `/health` endpoint for the Docker healthcheck
- The portal route at `/admin/` is excluded from JSON analytics in Nginx,
  so admin views don't pollute the visitor counts.

## What Step 2.5 will add

- Chart.js line chart of daily visitors
- Country breakdown
- Top referrers
- Hourly heatmap
- Per-IP session view

## Required environment

| Var | Purpose |
|-----|---------|
| `DATABASE_URL`      | PostgreSQL DSN (same as ingester) |
| `ADMIN_USERNAME`    | Username for Basic Auth |
| `ADMIN_PASSWORD`    | Password for Basic Auth |

## Layout

```
ml/admin-portal/
├── app/
│   ├── main.py                  ← FastAPI factory + router include
│   ├── auth.py                  ← HTTPBasic dependency (constant-time compare)
│   ├── db.py                    ← psycopg2 connection helper, RealDictCursor
│   ├── queries.py               ← all SQL in one place
│   ├── routes.py                ← GET / and GET /health
│   └── templates/
│       └── dashboard.html       ← single Jinja2 template
└── docker/Dockerfile
```

## Auth security notes

- `secrets.compare_digest` used for credential comparison (prevents timing attacks)
- Credentials live in `.env` (gitignored)
- HTTPS terminates at Nginx; the admin-portal container never sees raw HTTP
- For stronger auth later: layer Cloudflare Access on top (SSO via Google /
  Apple / email), or migrate to bcrypt-hashed passwords + a real auth library.
