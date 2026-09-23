# ADR-021: MLflow is publicly browsable, read-only

**Status:** Accepted
**Date:** September 2026
**Stage:** 2 (Synology Implementation)
**Supersedes:** ADR-012 Part 1, for MLflow only. Grafana and the MinIO consoles stay LAN-only as ADR-012 states.

## Context

ADR-012 Part 1 made every operational UI LAN-only: no Nginx route, no subdomain, and screen-share for showing it to anyone.

Practice drifted from that for MLflow:

- Phase 1 proxied the ML tracker publicly at `pandyahomelab.com/mlflow/` (plus the un-prefixed `/api/2.0/mlflow`, `/ajax-api/2.0/mlflow` and `/graphql` routes its browser JS calls).
- Phase 2a added the per-domain subdomain `mlflow-dl.pandyahomelab.com` for the DL tracker, routed through the Cloudflare Tunnel. The DL demos link visitors to it (`MLFLOW_PUBLIC_BASE_URL` in their `prediction_service.py`) so they can inspect the training runs behind a prediction.

The portfolio value ADR-012 had set aside ("here's my training history") turned out to be the point of these demos. But the exposure had no access control at all: on 2026-09-23 a review found that anyone on the internet could create, update or delete experiments, runs and registered models on both trackers.

## Decision

**MLflow is publicly browsable and read-only. Writes happen only from inside the platform.**

1. **Public reads.** Both trackers stay public: `pandyahomelab.com/mlflow/` for ML and `mlflow-dl.pandyahomelab.com` for DL. There is no authentication; anyone can browse experiments, runs, metrics and artifacts.
2. **No public writes.** Nginx gates every MLflow location with the `$mlflow_write_denied` map in `deployment/nginx/nginx.conf`:
   - `GET`, `HEAD` and `OPTIONS` pass.
   - `POST` passes only for `*/search` endpoints and `/graphql`, which the UI uses for reads. MLflow 3.11's GraphQL "mutations" are only `searchRuns`, `searchDatasets` and a no-op test.
   - Everything else returns 403.
3. **Writes go through the platform only.**
   - Services and training jobs log over the Docker domain networks (`http://ml-mlflow:5000`, `http://dl-mlflow:5000`).
   - The operator writes via LAN `192.168.1.152:5000` (ML). The DL tracker has no host port; operator writes to it go through an SSH tunnel or `docker exec`.
4. **Anything that stores data stays off the public path.** Postgres, Redis and the MinIO S3 API are bound to `127.0.0.1` on the host. The MinIO consoles (`:9001`, `:9003`) remain LAN-only per ADR-012.

## Alternatives considered

**Back to LAN-only, as ADR-012 wrote it (rejected).** This means removing the public routes and the `mlflow-dl` hostname, and dropping the demos' links to their training runs. It is the smallest attack surface, but it gives up a feature the DL demos are built around. Screen-share does not work for an unattended portfolio visitor.

**Public with Basic Auth, which ADR-012 Part 2 makes available (rejected).** Credentials would defeat the purpose: portfolio visitors could not browse. And the one real risk, anonymous writes, is fully handled by refusing write methods.

**Cloudflare Access in front of MLflow (deferred).** This gives identity-aware access without Nginx changes. It is worth revisiting if MLflow ever needs per-person access, but it adds an external dependency for no gain while the goal is anonymous read.

## Consequences

- Visitors can inspect the real training history behind each demo. The DL demo links work as designed.
- Anonymous writes are closed. Verified on 2026-09-23: create, delete, update, artifact `PUT` and a `../` traversal attempt return 403 on both hosts, while UI reads and searches return 200.
- **The allowlist must track MLflow upgrades.** A new MLflow version could add UI reads sent as `POST`, or GraphQL mutations that really do write. Before bumping the pinned MLflow image, recheck the GraphQL schema and click through the UI. Symptom of a missing entry: a UI panel fails with 403.
- **Everything in MLflow is public**, including run parameters, tags and artifacts. Do not log anything to MLflow that should not be on the internet.
- Operator changes cannot be made through the public UI, only from the LAN (ML) or an SSH tunnel (DL).

## Related ADRs

- **ADR-012** — Part 1 is superseded here for MLflow only. Parts 2–3 (Basic Auth mechanism, per-demo auth pattern) are unchanged.
- **ADR-016** — domain-level networks are the write path for services.
- **ADR-019** — Cloudflare Tunnel and domain routing, through which `mlflow-dl` is published.
