---
title: Docker Compose File Strategy & Build Context
status: Proposed (new)
context: |
  Phase 1a requires wiring ml-iris-knn project into the ml-network infrastructure. However,
  the docker-compose file structure is not yet specified:
  
  1. Should projects be in base compose or separate dev override?
  2. How do projects reference infrastructure services (postgres, minio, etc.)?
  3. What build context strategy for multi-project setup?
  4. How to handle local development (source mounts) vs production (ECR images)?
  5. How do domain compose files coordinate if needed?
decision: |
  Establish a three-tier docker-compose file hierarchy per domain:
  
  1. docker-compose.yml (base)      — Infrastructure services only (postgres, minio, redis, mlflow)
  2. docker-compose.dev.yml         — Dev override: adds project services with source mounts
  3. docker-compose.prod.yml        — Prod override: references ECR images (Phase 6+)
  
  Each domain folder (deployment/ml/, deployment/dl/, etc.) contains this structure.
  Projects added to dev override, not base compose, keeping infrastructure decoupled from project lifecycle.
  
  Build context and service networking defined per layer.
alternatives_considered: |
  A. Single compose file, all services always present — rejected, inflexible for iterative development
  B. Separate compose per project (ml-iris-knn/docker-compose.yml) — rejected, violates ADR-015
     (deployment separation)
  C. Three-tier hierarchy (chosen) — Base (infra) + Dev override (projects) + Prod override (ECR)
     provides flexibility, keeps concerns separated, works for all phases
consequences: |
  Positive:
  - Developers can spin up just infrastructure: `docker-compose up` (base)
  - Developers can add projects for development: `docker-compose -f docker-compose.yml -f docker-compose.dev.yml up`
  - Infrastructure changes don't require project code edits
  - Projects can be added/removed without touching base compose
  - Migration to production (Phase 6): just swap docker-compose.prod.yml
  - Clear separation: deployment/ owns orchestration, projects own code
  
  Negative:
  - Multiple compose files require discipline (which override to use when)
  - Docker Compose override syntax is not immediately obvious to new developers
  
  Mitigations:
  - Makefile targets provide shortcuts (make compose-dev, make compose-up)
  - README documents file hierarchy and when to use each
  - CI/CD enforces correct compose file usage
related_adrs: |
  - ADR-015 — Deployment service separation (compose files stay in deployment/)
  - ADR-016 — Domain-level network topology (services connect via networks)
  - ADR-020 — Project readiness checklist (TIER 2 includes docker-compose validation)
---

# ADR-017 — Docker Compose File Strategy & Build Context

**Status:** Proposed (new)  
**Date:** May 2026  
**Author:** Archit Pandya

## Context

Phase 1a requires integrating ml-iris-knn project into the ml-network infrastructure. The docker-compose file structure determines:

1. **When projects are deployed** — Always on? Only in dev? Injected at runtime?
2. **Service discovery** — How does ml-iris-knn find ml-postgres at 172.20.0.2?
3. **Build strategy** — Local builds (source mount) vs pre-built images?
4. **Environment parity** — Same compose for NAS dev, AWS staging, AWS production?

Without explicit strategy, developers improvise, leading to inconsistency.

## Decision

**Three-tier docker-compose hierarchy per domain:**

### Tier 1: Base Compose (`docker-compose.yml`)

Infrastructure services only. Shared across dev/staging/prod.

```yaml
# deployment/ml/docker-compose.yml
version: '3.8'

networks:
  ml-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/24
          gateway: 172.20.0.1

services:
  ml-postgres:    # 172.20.0.2
  ml-minio:       # 172.20.0.3
  ml-redis:       # 172.20.0.4
  ml-mlflow:      # 172.20.0.5
  # NO PROJECTS HERE

volumes:
  ml_postgres_data:
  ml_minio_data:
  ml_redis_data:
  ml_mlflow_data:
```

**Characteristics:**
- Infrastructure only (no project services)
- Fixed IP addresses per ADR-016 (172.20.0.2-5)
- Health checks for all services
- Restart policy: `unless-stopped`
- Persistent volumes for data

### Tier 2: Dev Override (`docker-compose.dev.yml`)

Adds project services with source code mounts.

```yaml
# deployment/ml/docker-compose.dev.yml
version: '3.8'

services:
  ml-iris-knn:
    build:
      context: ../../ml/ml-iris-knn
      dockerfile: docker/Dockerfile
    container_name: ml-iris-knn
    environment:
      DATABASE_URL: postgresql://postgres:password@ml-postgres:5432/mldb
      MINIO_ENDPOINT: ml-minio:9000
      REDIS_URL: redis://ml-redis:6379
      MLFLOW_TRACKING_URI: http://ml-mlflow:5000
      DEBUG: "true"
    ports:
      - "8000:8000"
    volumes:
      - ../../ml/ml-iris-knn/presentation-logic:/app/presentation-logic
      - ../../ml/ml-iris-knn/application-logic:/app/application-logic
      - ../../ml/ml-iris-knn/db-logic:/app/db-logic
      - ../../ml/ml-iris-knn/shared:/app/shared
      - ../../ml/ml-iris-knn/configs:/app/configs
    networks:
      ml-network:
        ipv4_address: 172.20.0.10
    depends_on:
      ml-postgres:
        condition: service_healthy
      ml-minio:
        condition: service_healthy
      ml-redis:
        condition: service_healthy
      ml-mlflow:
        condition: service_healthy
    restart: unless-stopped

  ml-housing:
    build:
      context: ../../ml/ml-housing
      dockerfile: docker/Dockerfile
    container_name: ml-housing
    environment:
      DATABASE_URL: postgresql://postgres:password@ml-postgres:5432/mldb
      MINIO_ENDPOINT: ml-minio:9000
      REDIS_URL: redis://ml-redis:6379
      MLFLOW_TRACKING_URI: http://ml-mlflow:5000
      DEBUG: "true"
    ports:
      - "8001:8000"
    volumes:
      - ../../ml/ml-housing/presentation-logic:/app/presentation-logic
      - ../../ml/ml-housing/application-logic:/app/application-logic
      - ../../ml/ml-housing/db-logic:/app/db-logic
      - ../../ml/ml-housing/shared:/app/shared
      - ../../ml/ml-housing/configs:/app/configs
    networks:
      ml-network:
        ipv4_address: 172.20.0.11
    depends_on:
      ml-postgres:
        condition: service_healthy
      ml-minio:
        condition: service_healthy
      ml-redis:
        condition: service_healthy
      ml-mlflow:
        condition: service_healthy
    restart: unless-stopped
```

**Characteristics:**
- Project services with fixed IPs per domain allocation scheme
- Source code mounted as volumes (hot reload for development)
- Environment variables point to infrastructure services (same network, hostname resolution works)
- Port mappings for local testing (8000, 8001, etc.)
- Depends on infrastructure health (ensures postgres, etc. are ready before project starts)
- DEBUG mode enabled for development

### Tier 3: Production Override (`docker-compose.prod.yml`)

Phase 6+ — References pre-built images from ECR (AWS) or registry.

```yaml
# deployment/ml/docker-compose.prod.yml
version: '3.8'

services:
  ml-iris-knn:
    image: 123456789.dkr.ecr.us-east-1.amazonaws.com/ml-iris-knn:v1.0.0
    container_name: ml-iris-knn
    environment:
      DATABASE_URL: postgresql://postgres:password@ml-postgres:5432/mldb
      MINIO_ENDPOINT: ml-minio:9000
      REDIS_URL: redis://ml-redis:6379
      MLFLOW_TRACKING_URI: http://ml-mlflow:5000
      DEBUG: "false"
    networks:
      ml-network:
        ipv4_address: 172.20.0.10
    depends_on:
      ml-postgres:
        condition: service_healthy
    restart: unless-stopped

  ml-housing:
    image: 123456789.dkr.ecr.us-east-1.amazonaws.com/ml-housing:v1.0.0
    container_name: ml-housing
    environment:
      DATABASE_URL: postgresql://postgres:password@ml-postgres:5432/mldb
      MINIO_ENDPOINT: ml-minio:9000
      REDIS_URL: redis://ml-redis:6379
      MLFLOW_TRACKING_URI: http://ml-mlflow:5000
      DEBUG: "false"
    networks:
      ml-network:
        ipv4_address: 172.20.0.11
    depends_on:
      ml-postgres:
        condition: service_healthy
    restart: unless-stopped
```

**Characteristics:**
- References ECR/registry images (no local build)
- No source code mounts (production is immutable)
- DEBUG mode disabled
- Same IPs, same network structure (zero code changes from dev→prod)

## Usage Patterns

### Pattern 1: Develop Infrastructure Only
```bash
cd deployment/ml/
docker-compose up
# Starts postgres, minio, redis, mlflow
# Developers can test infrastructure, migrations, etc. without projects
curl http://localhost:5000  # mlflow
```

### Pattern 2: Develop with Projects (Local)
```bash
cd deployment/ml/
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
# Starts infrastructure + ml-iris-knn + ml-housing
# Source code mounted, changes hot-reload
curl http://localhost:8000  # ml-iris-knn
curl http://localhost:8001  # ml-housing
```

### Pattern 3: Production Deployment (Phase 6+)
```bash
cd deployment/ml/
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up
# Starts infrastructure + pre-built images from ECR
# No local builds, immutable images
```

## Build Context Management

### Local Development Build
```dockerfile
# ml/ml-iris-knn/docker/Dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .  # Copy entire project
EXPOSE 8000
CMD ["uvicorn", "presentation_logic.api.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build context:** `ml/ml-iris-knn/` (includes all 3 layers, tests, configs, everything)

### CI/CD Build (pre-production)
Same Dockerfile, but build context validated:
- No uncommitted changes
- All tests pass (TIER 1, 2, 3)
- Image tagged with git commit hash

### Production Image
Same image used everywhere:
- Built once in CI/CD
- Tagged with version (v1.0.0)
- Pushed to ECR
- Deployed unchanged to staging, production

## File Organization

```
deployment/ml/
├── docker-compose.yml           (base infrastructure)
├── docker-compose.dev.yml       (dev: adds projects + source mounts)
├── docker-compose.prod.yml      (prod: ECR images)
├── docker-compose.staging.yml   (staging: ECR images, pre-prod validation)
├── .env.base                    (shared env vars)
├── .env.dev                     (dev overrides)
├── .env.prod                    (prod overrides)
├── nginx/
│   ├── nginx.conf
│   └── Dockerfile
└── services/
    ├── postgres/
    ├── minio/
    ├── redis/
    └── mlflow/
```

## Environment Variable Strategy

### .env.base (committed to git)
```bash
# Infrastructure endpoints (same for all)
ML_POSTGRES_DB=mldb
ML_POSTGRES_USER=postgres
ML_MINIO_ENDPOINT=ml-minio:9000
ML_REDIS_URL=redis://ml-redis:6379
ML_MLFLOW_TRACKING_URI=http://ml-mlflow:5000
```

### .env.dev (committed to git, development defaults)
```bash
ML_POSTGRES_PASSWORD=devpassword  # NEVER use in production
DEBUG=true
LOG_LEVEL=DEBUG
```

### .env.prod (NOT committed, secrets only)
```bash
ML_POSTGRES_PASSWORD=<secrets-manager>
DEBUG=false
LOG_LEVEL=INFO
```

**Usage:**
```bash
# Load all env files in order
docker-compose --env-file .env.base --env-file .env.dev config
```

## Service Discovery & Networking

All services on same domain network resolve by hostname:

```python
# Inside ml-iris-knn container
import psycopg2
conn = psycopg2.connect(
    host="ml-postgres",      # Resolved by Docker DNS to 172.20.0.2
    port=5432,
    database="mldb"
)
```

**Key:** Docker's embedded DNS resolver translates `ml-postgres` → `172.20.0.2` within ml-network.

## Constraints & Guardrails

1. **Fixed IPs:** Every service has ipv4_address defined (no auto-assignment)
   - Ensures consistency across restarts
   - Allows external monitoring to track services
   
2. **Health checks:** All infrastructure services have healthcheck
   - Projects depend_on infrastructure healthy status
   - Projects won't start if infrastructure is unhealthy
   
3. **Restart policy:** `unless-stopped` (automatic recovery)
   - If postgres crashes, it auto-restarts
   - If project crashes, it auto-restarts
   
4. **Logging:** All services use json-file driver
   - `docker logs ml-iris-knn` shows JSON-formatted logs
   - Parseable by monitoring tools
   
5. **Volumes:** Infrastructure data persists
   - Restart doesn't lose data
   - Developer can `docker-compose down` and `up` again, data survives

## Migration: NAS → AWS

**NAS (docker-compose.dev.yml):**
```yaml
ml-iris-knn:
  build:
    context: ../../ml/ml-iris-knn
  networks:
    ml-network:
      ipv4_address: 172.20.0.10
```

**AWS (Kubernetes via ECS/K8s, but compose structure same):**
```yaml
ml-iris-knn:
  image: ecr.../ml-iris-knn:v1.0.0
  networks:
    ml-network:
      ipv4_address: 10.0.1.10  # AWS subnet, same pattern
```

Same structure, different CIDR ranges. Infrastructure services on RDS/ElastiCache instead of local containers, but Docker Compose pattern transfers.

## Validation Checklist (TIER 2 — Docker Readiness)

```
[ ] docker-compose.yml validates: docker-compose config
[ ] Infrastructure services healthy: docker-compose up (wait 30s)
[ ] ml-postgres reachable: docker exec ml-iris-knn psql -h ml-postgres -U postgres -d mldb -c "SELECT 1"
[ ] ml-minio reachable: docker exec ml-iris-knn curl -f http://ml-minio:9000/minio/health/live
[ ] ml-redis reachable: docker exec ml-iris-knn redis-cli -h ml-redis ping
[ ] ml-mlflow reachable: docker exec ml-iris-knn curl -f http://ml-mlflow:5000/health
[ ] Projects start cleanly: docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
[ ] ml-iris-knn logs appear: docker logs ml-iris-knn | tail -20
[ ] Health endpoint works: curl http://localhost:8000/health
[ ] Project can connect to postgres: docker exec ml-iris-knn python -c "from db_logic.loaders.loaders import DatabaseDataLoader; DatabaseDataLoader('SELECT 1')"
```

## Related ADRs

- **ADR-015** — Deployment service separation (compose files in deployment/, not in projects)
- **ADR-016** — Domain-level network topology (fixed IPs, CIDR ranges)
- **ADR-020** — Project readiness checklist (TIER 2 includes compose validation)
- **ADR-018** — Development workflow (how developers use compose files day-to-day)

---

**Status: READY FOR IMPLEMENTATION**

Three-tier compose hierarchy provides flexibility from development through production. All services auto-discover on same network. Infrastructure and projects clearly separated.
