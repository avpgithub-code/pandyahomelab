# analytics-ingester

Tails the Nginx JSON access log, enriches each event (salted IP hash + bot detection),
and writes the result to `analytics.visitor_events` in `ml-postgres`.

## What it does

1. Tails `/logs/access.json.log` (bind-mounted from the host) by byte offset
2. Parses each JSON line into a typed event dict
3. Hashes the visitor IP — prefers `cf_connecting_ip` (real visitor via Cloudflare),
   falls back to `remote_addr`. SHA-256 with a salt from `ANALYTICS_IP_SALT`.
   The raw IP never reaches the database.
4. Detects bots by user-agent substring matching (Googlebot, curl, etc.)
5. Batch-inserts into PostgreSQL via `psycopg2.execute_batch`
6. Persists the byte offset + inode atomically to `/checkpoint/state.json`
   so restarts don't re-ingest history or miss new lines
7. Detects log rotation by inode change and resets to offset 0

## Required environment

| Var | Purpose | Notes |
|-----|---------|-------|
| `DATABASE_URL`        | PostgreSQL DSN | e.g. `postgresql://postgres:pass@ml-postgres:5432/mldb` |
| `ANALYTICS_IP_SALT`   | Salt for SHA-256 of visitor IPs | Generate with `openssl rand -hex 32`; keep stable for cross-day visitor identity |
| `LOG_PATH`            | Path to Nginx JSON log inside container | Default `/logs/access.json.log` |
| `CHECKPOINT_PATH`     | Where to persist the offset | Default `/checkpoint/state.json` |
| `POLL_INTERVAL_SECONDS` | How often to check for new lines | Default `2` |
| `LOG_LEVEL`           | Python logging level | Default `INFO` |

## Schema

Created on first startup, idempotent. See `ingester/schema.py`.

Single table `analytics.visitor_events` with five tuned indexes for the dashboard
queries (recent events, per-path counts, per-IP sessions, per-country aggregations,
"real visitor" filtering).

## Operations

- **Restarts safely** — checkpoint resumes from last saved offset
- **Survives log rotation** — inode change resets to offset 0
- **Accepts duplicates** — V1 prioritizes simplicity; on rare crash between
  insert and checkpoint, a handful of duplicate rows may appear. Easy to dedupe
  later via `SELECT DISTINCT` in reports.
- **Crashes are logged** — `restart: unless-stopped` handles unexpected exits
