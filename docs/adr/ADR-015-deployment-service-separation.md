---
title: Deployment service separation — orchestration decoupled from projects
status: Proposed (new)
context: |
  ADR-007 (V3 revision) establishes that ml/ and dl/ folders contain autonomous projects.
  But where does Docker Compose live? Where does Nginx config go?
  
  Stage 2 mixed these concerns: platform/ contained both infrastructure services (Nginx, Postgres)
  and placeholder for projects.
  
  V3 principle: clear separation between "what runs" (projects) and "how it's orchestrated" (deployment).
decision: |
  Create deployment/ folder housing all orchestration and infrastructure:
  
  deployment/
  ├── docker-compose.yml       (main orchestration: proxy, postgres, minio, redis, mlflow, grafana)
  ├── docker-compose.dev.yml   (dev overrides: adds ml/dl project services, NAS mounts)
  ├── docker-compose.staging.yml
  ├── docker-compose.prod.yml
  ├── nginx/
  │   ├── Dockerfile           (Nginx base image + config)
  │   ├── nginx.conf           (reverse proxy, path-based routing per ADR-005)
  │   └── .dockerignore
  ├── services/                (shared infrastructure services)
  │   ├── postgres/
  │   ├── minio/
  │   ├── redis/
  │   └── mlflow/
  ├── envs/                    (environment-specific configs)
  │   ├── dev.env
  │   ├── staging.env
  │   └── prod.env
  ├── Makefile                 (deployment targets: make up, make down, make logs)
  └── README.md                (how to deploy to NAS, AWS)
  
  Invariant: deployment/ contains ZERO project code. Projects (ml/, dl/) are called as services in compose,
  referenced only through image names (e.g., ml-iris-knn:latest pulled from ECR).
alternatives_considered: |
  A. Keep platform/ folder, mix infrastructure and projects — rejected, violates separation of concerns
  B. Embed compose in each project — rejected, orchestration is global not per-project
  C. Dedicated deployment/ folder (chosen) — clear separation, scales with new projects
consequences: |
  Positive:
  - Clear separation: "what" (projects) vs. "how" (deployment)
  - Deployment strategy can change without touching project code
  - Easy to add new orchestration tools (Kubernetes later?)
  - Portfolio viewers immediately understand: projects are independent; deployment is separate
  - Developers can run single project locally without full stack
  
  Negative:
  - One more top-level folder (acceptable for clarity)
  
  Deferred:
  - Kubernetes migration strategy (Stage 5)
  - Multi-cluster deployment (Stage 5)
related_adrs: |
  - ADR-007 (V3 revision) — repository layout (deployment/ is one of 8 root folders)
  - ADR-005 — path-based routing (Nginx config lives in deployment/nginx/)
  - ADR-006 — Nginx replaces DSM proxy (Nginx service in deployment/services/)
  - ADR-012 — authentication strategy (LAN-only UIs coordinated in deployment/)
---

# ADR-015 — Deployment Service Separation

**Status:** Proposed (new)  
**Date:** May 2026  
**Author:** Archit Pandya

## Context

ADR-007 (V3 revision) establishes that `ml/` and `dl/` folders contain autonomous projects.

**Question:** Where does the glue go? Docker Compose orchestrates everything. Nginx reverse proxy routes requests. These are infrastructure concerns, not project concerns. Where do they live?

**Stage 2 approach:** Mixed infrastructure into `platform/`, side-by-side with placeholder project folders.

**Problem:** Infrastructure and projects became tangled in perception. GitHub viewers see "platform" and don't immediately understand: "Oh, projects are separate; this is just orchestration."

## Decision

Create a dedicated `deployment/` folder housing ALL orchestration, infrastructure services, and environment configs.

```
deployment/
├── docker-compose.yml           (base: proxy, db, cache, mlops)
├── docker-compose.dev.yml       (adds ml/dl project services, NAS mounts)
├── docker-compose.staging.yml   (AWS staging overrides)
├── docker-compose.prod.yml      (AWS production overrides)
├── nginx/
│   ├── Dockerfile               (Nginx Alpine image + config)
│   ├── nginx.conf               (reverse proxy, path-based routing)
│   ├── certs/                   (TLS certificates, if local dev)
│   └── .dockerignore
├── services/                    (shared infrastructure)
│   ├── postgres/
│   │   ├── Dockerfile           (if custom image)
│   │   └── init.sql             (schema initialization)
│   ├── minio/
│   │   └── Dockerfile           (if custom)
│   ├── redis/
│   │   └── Dockerfile           (if custom)
│   └── mlflow/
│       ├── Dockerfile
│       └── entrypoint.sh
├── envs/                        (environment-specific variables)
│   ├── dev.env                  (development overrides)
│   ├── staging.env              (staging AWS overrides)
│   └── prod.env                 (production AWS overrides)
├── Makefile                     (deployment tasks)
├── README.md                    (deployment documentation)
└── .env.example                 (template for all environments)
```

### Key Invariant

**`deployment/` contains ZERO project code.**

Projects (`ml/ml-iris-knn/`, `dl/dl-lstm-forecast/`) are REFERENCED in compose files as services, built as Docker images, pulled from container registry (ECR). But their source code never lives in `deployment/`.

### How It Works

1. **Development (NAS):**
   ```bash
   cd deployment/
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
   ```
   - Runs base services (Nginx, Postgres, MinIO, Redis, MLflow)
   - Plus mounted ml/ and dl/ projects from source tree (no containerization, direct Python)
   - Good for rapid iteration

2. **Staging (AWS EC2):**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.staging.yml up
   ```
   - Base services on EC2 instances
   - ml/dl projects pulled from ECR as built images
   - Configuration from `envs/staging.env`

3. **Production (AWS EC2):**
   - Similar to staging, configuration from `envs/prod.env`
   - Potentially different resource limits, auto-scaling

### Docker Compose Strategy

**Base (`docker-compose.yml`):**
```yaml
services:
  proxy:
    build: ./nginx
    ports: [80:80, 443:443]
  
  postgres:
    image: postgres:16-alpine
    environment_file: ./envs/dev.env
    # ... etc
  
  minio:
    image: minio/minio
    # ... etc
  
  mlflow:
    build: ./services/mlflow
    # ... etc
```

**Dev override (`docker-compose.dev.yml`):**
```yaml
services:
  ml-iris-knn:
    build: ../ml/ml-iris-knn
    volumes: [../ml/ml-iris-knn:/workspace]
  
  dl-lstm-forecast:
    build: ../dl/dl-lstm-forecast
    volumes: [../dl/dl-lstm-forecast:/workspace]
```

**AWS override (`docker-compose.prod.yml`):**
```yaml
services:
  ml-iris-knn:
    image: 123456789.dkr.ecr.us-east-1.amazonaws.com/ml-iris-knn:latest
    # (no build, image pulled from ECR)
```

## Alternatives Considered

### A. Keep Stage 2 `platform/` Structure
```
platform/proxy/
platform/data/
services/ml/classification/iris-knn/
```
**Rejected** — Mixes infrastructure and projects; unclear separation.

### B. Embed Compose in Each Project
**Rejected** — Orchestration is global, not per-project. Would duplicate compose files.

### C. Dedicated `deployment/` Folder
**Chosen** — Clear separation, scales as projects accumulate, future-proof for new orchestration tools.

## Consequences

### Positive
- **Clear separation of concerns** — "what runs" (projects) vs. "how it's run" (deployment)
- **Scalability** — Adding 20 projects doesn't clutter deployment/; it just adds compose services
- **Portfolio clarity** — GitHub viewers immediately see: projects are independent; deployment is infrastructure
- **Flexibility** — Deployment strategy can evolve (Kubernetes later?) without touching project code
- **Testability** — Developers can run a single project locally without the full stack

### Negative
- **One more top-level folder** — 8 folders instead of 7 (negligible)
- **Compose complexity might grow** — As projects accumulate, compose files get larger
  - *Mitigation:* Split into `docker-compose.services.yml`, `docker-compose.projects.yml` if needed (future)

### Deferred
- **Kubernetes migration** — Could create `infra/k8s/` for Kubernetes manifests later (Stage 5)
- **Multi-cluster deployment** — Stage 5 concern

## Related ADRs

- **ADR-007** (V3 revision) — Repository layout (deployment/ is one of 8 root folders)
- **ADR-005** — Path-based routing (Nginx config in deployment/nginx/)
- **ADR-006** — Nginx replaces DSM proxy (Nginx service in deployment/)
- **ADR-012** — Authentication strategy (LAN-only UI coordination in deployment/)
- **ADR-008** — Repository packaging (still single monorepo, just organized better)

---

**First Implementation:** Iris-KNN will be registered as a service in `deployment/docker-compose.dev.yml`, callable via `docker-compose up`.
