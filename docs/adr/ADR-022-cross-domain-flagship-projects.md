# ADR-022: Cross-domain flagship projects (cricstat)

**Status:** Accepted (2026-10-05)
**Date:** October 2026
**Stage:** 2 (Synology Implementation)
**Amends:** ADR-016 (Amendment 2: a new network and port block), ADR-003 (a new L2 path family). **Relates to:** ADR-008, ADR-013, ADR-015, ADR-019.

## Context

Every project so far is one technique in one container, inside one domain (`/ml/`, `/dl/`, `/nlp/`, `/agentic/`).
cricstat is different:
- It spans a data pipeline, ML and DL models, NLP, and an LLM agent.
- It has several pages and two always-on services.
- It has scheduled batch jobs and a shared serving database.

Putting it under any one domain would misdescribe it, and splitting it across domains would scatter one product's
code, data and deployment. The product design is in `cricstat/docs/F1`–`F5`.

## Decision

**pandyaHomeLab gains a "flagship project" category for cross-domain products. cricstat is the first.**

1. **Code:** a top-level folder in the monorepo, `cricstat/`, holding the project's services. Each service keeps the
   4-layer structure (ADR-013) and its own Dockerfile, tests and README. Shared SQL lives in `cricstat/sql/`.
   Deployment config lives in `deployment/cricstat/` (ADR-015).
2. **URLs (ADR-003 extension):** the flagship gets its own L2 path, `/cricket/`.
   - Static pages are served by Nginx from `cricstat/web/`, mounted read-only at `/var/www/html/cricket`.
   - `/cricket/api/` → `cricstat-api`.
   - `/cricket/ask/api/` → `cricstat-agent` (Server-Sent Events, `proxy_buffering off`).
   - The domain landing pages link to the flagship with cross-link cards. They don't host it.
3. **Network (ADR-016 Amendment 2):** a new bridge network, `cricstat-network`, **172.25.0.0/24**.
   Docker name `cricstat_cricstat-network`. Domain index 4.
   | Address | Container | Host port | Role |
   |---|---|---|---|
   | .10 | cricstat-api | 127.0.0.1:8040 | Always-on |
   | .11 | cricstat-agent | 127.0.0.1:8041 | Always-on, P4 |
   | .12 | cricstat-phoenix | 127.0.0.1:8042 (UI by SSH tunnel) | Tracing, P4 |
   | .13 | cricstat-mcp | none | Reserved, P6 |
   | .14 | cricstat-pipeline | none | Batch: runs and exits |
   | .15 | cricstat-models | none | Batch: runs and exits |
   | .20 | pandya-nginx leg | — | Reverse-proxy attachment |

   - No Postgres, MinIO or Redis: SQLite files only.
   - **New range on domain networks:** `.40–.49` for cross-domain legs. `cricstat-models` joins `ml-network` at
     **172.20.0.40**, to log to `ml-mlflow` with `cricstat-*` experiment names (no fourth MLflow tracker).
4. **Egress:** only `cricstat-agent` needs outbound internet (the Anthropic API). `cricstat-pipeline` needs it for
   Cricsheet and Wikidata downloads. Platform bridge networks already allow egress. Nothing becomes reachable from the
   internet except through Nginx (ADR-016 invariant unchanged).
5. **Data:** bind mounts of `cricstat/data/`.
   | Path | Contents | Access |
   |---|---|---|
   | `data/raw/`, `data/db/raw.sqlite` | Downloads and the raw store | pipeline rw |
   | `data/db/cricstat.sqlite` | Serving DB, swapped in atomically | pipeline rw; api and agent **ro** |
   | `data/agent/` | LangGraph checkpointer and chat logs (30-day retention) | agent rw |

   The **directory** is mounted, not the file. A file bind mount pins the inode, so readers would never see the swapped file.
6. **Secrets:** follow current practice. `deployment/cricstat/.env` is gitignored and holds `ANTHROPIC_API_KEY` and the
   budget caps. It is mode **600**, as ADR-010 requires. A committed `.env.example` documents every variable.
7. **Schedules:** DSM Task Scheduler runs `docker compose run --rm` for batch jobs. A non-zero exit triggers DSM's email
   on abnormal termination, like the tunnel alert. Times are in `cricstat/docs/F6-engineering-setup.md`.

## Alternatives considered

- **Host cricstat under `/agentic/` or `/ml/` (rejected).** It misdescribes a multi-domain product, and the
  progressive-disclosure hierarchy (ADR-003) would mislead.
- **Subdomain `cricket.pandyahomelab.com` (rejected for now).** It is cleaner for a JS-heavy app, but weaker for
  discoverability, which matters most for this site. ADR-005's triggers are noted. Revisit if the API gains
  non-browser consumers at scale.
- **Separate repo or site (rejected).** It splits recruiter traffic and breaks ADR-008. It doubles operations.
- **Reuse `agentic-network` (rejected).** It is reserved for Phase 4 domain demos. Sharing it would blur trust
  boundaries between unrelated projects.
- **Its own MLflow tracker (rejected).** It costs about 0.5 GB RAM on a NAS with about 7 GB free. Experiment
  prefixes on `ml-mlflow` give the same separation.

## Consequences

- Positive:
  - A new kind of portfolio item: an end-to-end product next to technique demos.
  - Isolation by network, with the same Nginx and tunnel patterns.
  - Only two always-on containers (about 0.5–0.7 GB).
- Negative:
  - One cross-domain leg (`cricstat-models` on `ml-network`). This is a small, documented trust-boundary exception.
    Mitigated by the leg being a batch job that runs only on schedule.
- `docs/NETWORK_CIDR_SUMMARY.md` §1, §3, §6a and §11 record the allocation (ADR-016 Amendment 2, 2026-10-05).
