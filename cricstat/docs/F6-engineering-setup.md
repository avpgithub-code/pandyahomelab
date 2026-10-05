# F6 — cricstat engineering setup

Status: **approved** (2026-10-05). The pipeline is deployed (see §8). Architecture decision: [ADR-022](../../docs/adr/ADR-022-cross-domain-flagship-projects.md) (Proposed).
This is how cricstat is laid out, built, run and tested on the NAS, following the platform's existing conventions.

## 1. Repository layout
```
cricstat/
├── CLAUDE.md, README.md           decisions + overview
├── docs/                          F1–F9, wireframes/, validation/ (golden figures, later)
├── sql/                           serving_schema.sql, reference_data.sql, semantic_views.sql  (shared by services)
├── web/                           static /cricket/ pages (Nginx serves them, read-only)          ← P0
├── cricstat-pipeline/             ingest (done) + build (P0) — batch
├── cricstat-api/                  FastAPI, GET-only, reads serving DB read-only                ← P0
├── cricstat-models/               Elo / ML / DL predictor, sequence model; logs to ml-mlflow    ← P1
├── cricstat-agent/                LangGraph agent, SSE, tools → cricstat-api                    ← P4
├── cricstat-mcp/                  MCP server over the same tools                               ← P6
├── data/  logs/                   runtime only (gitignored)
deployment/cricstat/               docker-compose.yml (draft committed), .env.example, .env (gitignored, 600)
.github/workflows/cricstat-ci.yml  CI skeleton (committed with F6)
```
Every service: 4-layer structure (ADR-013), `docker/Dockerfile` on `python:3.12-slim`, its own `tests/`, README and
CHANGELOG, mirroring `cricstat-pipeline/`. **Build context change:** services that need `cricstat/sql/` (pipeline `build`,
api) will build from context `cricstat/` with `-f <service>/docker/Dockerfile`, so the SQL is copied into the image.

## 2. Containers and network
From ADR-022:
- **Network:** `cricstat-network`, 172.25.0.0/24.
- **Always on (2):** `cricstat-api` (.10, :8040) and `cricstat-agent` (.11, :8041, P4).
- **Batch, run and exit:** `cricstat-pipeline` (.14) and `cricstat-models` (.15, plus `ml-network` .40 for MLflow).
- **Tracing:** Phoenix (.12, P4).
- **Memory budget:** about 0.5–0.7 GB always-on, plus about 1 GB for Phoenix at P4. That fits the ~7 GB free.

**Pre-flight check on the live NAS (2026-10-05): no conflicts.**
- **Docker networks in use:** 172.17/16 (default bridge), 172.20, 172.21, 172.22 and 172.24. 172.23 is reserved for
  agentic and not created.
- **Host routes:** LAN 192.168.1.0/24 and OpenVPN 10.8.0.0/24. **172.25.0.0/24 is unused.**
- **ml-network** uses .2–.5, .10–.12, .20, .30 and .31, so **172.20.0.40 is free.**
- **Host ports in use:** 8001–8003, 8010–8011, 8020–8023 and 8080. **8040–8049 are free.**
- **Names:** no container or image named `cricstat-*` exists.
- **Guard:** the compose file declares the subnet explicitly, so Docker never auto-assigns a different one.
- **Recheck before every deploy:** `docker network ls`, `ip route` and `ss -ltn`.
- **DSM firewall (reviewed 2026-10-05): no change needed.**
  - Public traffic arrives through the Cloudflare Tunnel, which is outbound.
  - Host ports bind to 127.0.0.1.
  - Container-to-host traffic is allowed by the existing `172.16.0.0/12` rule, which covers 172.25.
  - Egress to Cricsheet, Wikidata and Anthropic is outbound.
  - **P4/P5 hardening item:** before the agent goes public, add a DSM deny rule for `172.25.0.0/24` placed *above*
    the `172.16.0.0/12` allow, so containers that handle visitor input cannot open connections to DSM/host services.
    Test it with the stack running, since rule order matters.

**Nginx changes** (when `cricstat-api` exists, not before; an upstream with no container crashes Nginx):
```nginx
upstream cricstat_api   { server 172.25.0.10:8000; }
location /cricket/      { alias /var/www/html/cricket/; try_files $uri $uri/ =404; }   # static, cache like the homepage
location /cricket/api/  { limit_req zone=cricstat_api burst=20 nodelay; proxy_pass http://cricstat_api/; }
# P4:
location /cricket/ask/api/ { proxy_buffering off; proxy_read_timeout 120s; proxy_pass http://cricstat_agent/; }
```
Plus a `limit_req_zone $http_cf_connecting_ip zone=cricstat_api:1m rate=10r/s;`, a pandya-nginx leg on
cricstat-network at .20, and the bind mount `cricstat/web → /var/www/html/cricket:ro`. Nginx is rebuilt with `--no-cache`
(nginx.conf is baked into the image).

## 3. Data, permissions and the database swap
- **Bind mounts:** `cricstat/data` and `cricstat/logs`.
- **Container user:** the operator's UID (`user: "${HOST_UID}:${HOST_GID}"` = 1026:100, ADR-009), so files stay editable.
  This overrides the uid 1000 baked into the image.
- **API and agent** mount `data/db/` read-only, as a **directory** (a file mount would hide the swapped file).
- **Swap:** the pipeline writes `cricstat.sqlite.new`, runs its checks, then `os.replace`. The API notices the new
  `build_info.build_id` and reopens.
- **Synology ACL:** `cricstat/` inherits the share ACL (fixed 2026-10-05). New top-level folders must show a `+`.

## 4. Schedules (DSM Task Scheduler, run as root, email on abnormal termination)
| When (NAS local time) | Command | Phase |
|---|---|---|
| Daily 05:30 | `run --rm cricstat-pipeline recent`, then `build --incremental` | ingest now; build from P0 |
| Daily 05:50 | `run --rm cricstat-models ratings` (Elo update + re-simulate if new ODIs) | P1 |
| Sunday 06:00 | `run --rm cricstat-pipeline register` (people.csv, names.csv + Wikidata for new ids) | P0 |
| 1st of month 04:00 | `run --rm cricstat-pipeline full`, then `build --full` | ingest now; build from P0 |
| Weekly / manual | `run --rm cricstat-models train` (ML/DL challengers, sequence model) | P1+ |

The jobs are sequential and the daily one runs early in the morning, out of visitors' peak hours. Exit codes from
the pipeline (0 / 1 / 2) drive the DSM email alert.

## 5. Secrets and configuration
- `deployment/cricstat/.env` (gitignored, **chmod 600**) holds `ANTHROPIC_API_KEY` (P4) and the budget, limit and
  retention settings. A committed `.env.example` documents every variable.
- No secret ever goes in images, the repo, logs or CI. CI has no secrets until the eval gate (P3/P4) needs one, as a
  GitHub Actions secret with its own small budget.
- **Platform finding (not cricstat):** `deployment/ml/.env` and `deployment/dl/.env` are currently world-readable
  (`rwxrwxrwx`), while ADR-010 requires `600`. Recommend `chmod 600` on both. Left for the operator to decide.

## 6. Development workflow
- **Branch and merge:** the platform pattern. Feature branch, `--no-ff` merge to `main`, tag
  `v.cricstat-<service>-<x.y.z>` when a service ships.
- **Local runs:** stdlib services run on the NAS host (Python 3.8), e.g.
  `python3 -m presentation_logic.cli recent` from `cricstat-pipeline/`. Services that need 3.10+ (agent, api with
  FastAPI) run in their container.
- **Tests:**
  | Type | Where | When |
  |---|---|---|
  | Unit | Each service's `tests/` | Always offline |
  | F4 metric fixtures | — | Build-step tests |
  | Golden figures | — | After a full build |
  | Agent evals | — | P3 |
- **Lint:** `ruff check` (line length 100, py38 target for the pipeline).

## 7. CI skeleton (`.github/workflows/cricstat-ci.yml`)
- **Trigger:** push or PR touching `cricstat/**`, `deployment/cricstat/**` or the workflow itself. Read-only permissions.
- **Job 1:** ruff + pytest for `cricstat-pipeline` on **Python 3.8 and 3.12**. This closes the "untested on 3.12" gap.
- **Job 2:** build the pipeline image (no push) and smoke-test `--help` inside it.
- **Not yet:** pushing images to GHCR, the NAS-side pull-based deploy, and the eval gate. Those are F9/P5, as planned.

## 8. Deployment steps (when approved — each `sudo docker` call needs your OK)
1. `cp deployment/cricstat/.env.example deployment/cricstat/.env && chmod 600 deployment/cricstat/.env`
2. `sudo docker compose -f deployment/cricstat/docker-compose.yml build cricstat-pipeline`
3. `sudo docker compose -f deployment/cricstat/docker-compose.yml run --rm cricstat-pipeline recent`
   This creates cricstat-network and proves the container works against the real data.
4. Create the daily DSM task (§4). Amend `NETWORK_CIDR_SUMMARY.md` and mark ADR-022 Accepted.

**Deployed 2026-10-05:**
- `.env` is created with mode 600.
- The image is built. The first container run (run 4, `recent`) succeeded with exit 0, and its files are owned by 1026:100.
- `cricstat_cricstat-network` (172.25.0.0/24) is created.
- **Fix found on the first run:** Synology's POSIX bits are 700 (ACLs grant the real access), and `COPY` keeps them, so the
  non-root user couldn't read `/app`. The Dockerfile now runs `chmod -R a+rX /app`. **Every cricstat Dockerfile needs this.**
- **DSM tasks** are created by the operator in the DSM UI (Control Panel → Task Scheduler). The settings are in CLAUDE.md.

## 9. Review decisions (2026-10-05)
1. ADR-022 accepted. NETWORK_CIDR_SUMMARY and ADR-016 Amendment 2 are updated.
2. Pipeline deployed now.
3. ML/DL `.env` permissions: awaiting the operator's yes or no.
4. The DSM firewall deny rule for 172.25.0.0/24 is on the P4/P5 security checklist in CLAUDE.md.
