---
title: Project Readiness Checklist & Phase Gates
status: Proposed (new)
context: |
  V3 architecture and network topology are locked. Now we need explicit criteria for when
  a project is "ready to deploy" to ensure quality baseline. Each project across all four
  domains (ML, DL, NLP, Agentic) must pass same checklist before moving from development
  to staging.
decision: |
  Establish a three-tier readiness model:
  
  TIER 1 — Code Readiness (project code passes local tests)
  TIER 2 — Docker Readiness (project builds and runs in container)
  TIER 3 — Integration Readiness (project healthy in Nginx routing, passes e2e tests)
  
  Each tier has specific checklist items. A project must pass TIER 1 before TIER 2,
  and TIER 2 before TIER 3. TIER 3 completion = Phase 1 complete, ready for Phase 2.
  
  Checklist is versioned and lives at docs/project-readiness-checklist.md
  Each project documents completion date and who verified.
alternatives_considered: |
  A. No checklist, just "looks good" — rejected, inconsistency risk, hard to onboard new projects
  B. Heavy gate process (sign-offs, multiple reviews) — rejected, overkill for solo development
  C. Lightweight self-service checklist (chosen) — developer verifies, documents, moves forward
consequences: |
  Positive:
  - Ensures consistent quality baseline across all projects
  - Clear exit criteria for each phase (no ambiguity about "ready")
  - Self-service (developer checks boxes, no bottleneck)
  - Scales (same checklist for project 1 and project 50)
  - Portfolio value (documentation of quality at each stage)
  
  Negative:
  - Developer must do the checking (not automated)
  - Checklist maintenance (as best practices evolve, must update)
  
  Mitigations:
  - CI/CD automates as much as possible (lint, test, build checks)
  - Runbooks provide step-by-step verification for manual checks
related_adrs: |
  - ADR-014 — Project autonomy and templates (templates include all TIER 1/2/3 tools)
  - ADR-013 — Per-project 3-layer architecture (structure reviewed in TIER 1)
  - ADR-015 — Deployment service separation (Nginx routing tested in TIER 3)
---

# ADR-020 — Project Readiness Checklist & Phase Gates

**Status:** Proposed (new)  
**Date:** May 2026  
**Author:** Archit Pandya

## Context

V3 architecture locks repository structure, network topology, and domain isolation. Before deploying a project to production (AWS), it must pass clear readiness criteria. Without explicit gates, projects may ship incomplete or with hidden technical debt.

**Goal:** Establish lightweight, developer-friendly checklist that ensures quality baseline across all four domains (ML, DL, NLP, Agentic AI).

## Decision

Three-tier readiness model with explicit pass/fail criteria at each tier.

### TIER 1: Code Readiness

**Gate:** Project code passes tests, linting, type checking locally.

**Checklist:**

```
[ ] Code Structure (per ADR-013)
    [ ] presentation-logic/ folder exists with api/, errors/ subfolders
    [ ] application-logic/ folder exists with model/, pipeline/, services/
    [ ] db-logic/ folder exists with loaders/, transforms/, repository/
    [ ] shared/ folder exists (project-local, not root-level)
    [ ] tests/ folder exists with presentation/, application/, db/ subfolders

[ ] Code Quality
    [ ] All Python files pass black formatting (make lint runs clean)
    [ ] All Python files pass flake8 linting (max-line-length 100, ignore E501)
    [ ] All Python files pass mypy type checking (optional: non-strict)
    [ ] No unresolved imports
    [ ] No debug print() statements

[ ] Testing
    [ ] Unit tests pass: make test-unit (pytest tests/ -m unit)
    [ ] All test files named test_*.py or *_test.py
    [ ] Test coverage > 70% (checked with: pytest --cov)
    [ ] No flaky tests (run 3x, all pass)
    [ ] Fixtures defined in conftest.py

[ ] Dependencies
    [ ] pyproject.toml exists with project metadata (name, version, author)
    [ ] requirements.txt lists all direct dependencies
    [ ] requirements-dev.txt lists dev-only dependencies (pytest, black, flake8, mypy)
    [ ] No version conflicts (pip check returns clean)
    [ ] No security vulnerabilities (pip audit clean)

[ ] Configuration
    [ ] .env.example exists with all required variables (no secrets in file)
    [ ] configs/model.yaml exists (if applicable) with sensible defaults
    [ ] configs/api.yaml exists with port, debug, timeout settings
    [ ] shared/config.py reads from environment + YAML files

[ ] Documentation
    [ ] README.md exists, explains project purpose and how to run
    [ ] README includes: project name, description, architecture, how to run locally
    [ ] CHANGELOG.md exists (at least one entry: "Initial project scaffold")
    [ ] Docstrings on public functions (api routes, model.py classes)
    [ ] No TODO comments left in code (or marked as [TODO: description])

[ ] Git
    [ ] Project committed to git at ml/ml-{project-name}/ (or dl/, nlp/, agentic/)
    [ ] .gitignore includes: __pycache__/, *.pyc, .env, data/, models/, .DS_Store
    [ ] README.md and .gitignore committed
```

**Verification:** Developer runs locally:
```bash
cd ml/ml-iris-knn
make lint      # black, flake8, mypy
make test-unit # pytest tests/ -m unit
pip check
pip audit
git status     # clean
```

**Owner:** Developer  
**Timeline:** ~2 hours per project

---

### TIER 2: Docker Readiness

**Gate:** Project builds and runs in container, all services healthy.

**Checklist:**

```
[ ] Dockerfile
    [ ] Dockerfile exists at project root (or docker/Dockerfile)
    [ ] Multi-stage build: base (dependencies) → runtime (app only)
    [ ] Base image specified (python:3.11-slim recommended)
    [ ] No secrets hardcoded (all from environment)
    [ ] WORKDIR set correctly (/app)
    [ ] ENTRYPOINT or CMD specified

[ ] Build
    [ ] Docker builds cleanly: docker build -t ml-iris-knn .
    [ ] Final image size < 500MB (check: docker images)
    [ ] No warnings during build

[ ] Container Startup
    [ ] Container starts: docker run -p 8000:8000 ml-iris-knn
    [ ] Service listens on correct port (8000 by default)
    [ ] GET /health returns 200 OK within 5 seconds
    [ ] Logs are JSON formatted to stdout (not written to files)

[ ] Environment Configuration
    [ ] All config read from environment variables
    [ ] .env.example documented
    [ ] Container runs without .env file (uses defaults)

[ ] Health Checks
    [ ] GET /health endpoint exists (returns JSON)
    [ ] GET /health responds within 1 second
    [ ] GET /health includes: status, timestamp, version
    [ ] Health check never requires database (or uses connection pool timeout)

[ ] Logging
    [ ] Application logs to stdout (not files)
    [ ] Log format: JSON (one object per line)
    [ ] Log includes: timestamp, level, message, request_id (if applicable)
    [ ] No sensitive data in logs (passwords, API keys)

[ ] docker-compose Integration
    [ ] Service added to deployment/{domain}/docker-compose.yml
    [ ] Service name matches container name: ml-iris-knn
    [ ] Service assigned fixed IP: ipv4_address: 172.20.0.10 (or appropriate .x)
    [ ] Service connected to correct domain network (ml-network)
    [ ] Service has healthcheck block
    [ ] Service has restart: unless-stopped

[ ] Makefile Targets
    [ ] make docker-build runs docker build correctly
    [ ] make docker-run starts container with port mappings
    [ ] make docker-logs shows live container logs
    [ ] make docker-stop stops container cleanly
    [ ] make docker-shell opens bash into running container

[ ] Testing in Container
    [ ] docker-compose up -d ml-postgres ml-{project}
    [ ] curl http://localhost:8000/health returns 200
    [ ] Integration test passes (connects to postgres in container)
    [ ] docker-compose down cleans up
```

**Verification:** Developer runs:
```bash
cd ml/ml-iris-knn
make docker-build
docker images | grep ml-iris-knn   # verify size, tags
make docker-run
curl http://localhost:8000/health
# In another terminal:
docker ps | grep ml-iris-knn       # verify running
make docker-logs                    # verify output
make docker-stop
```

**Owner:** Developer (with DevOps review if applicable)  
**Timeline:** ~1 hour per project

---

### TIER 3: Integration Readiness

**Gate:** Project integrates with Nginx, passes end-to-end tests, ready for staging.

**Checklist:**

```
[ ] Nginx Routing (ADR-019)
    [ ] Nginx upstream configured for project
    [ ] Upstream location: /ml/ → ml-iris-knn (or applicable domain/path)
    [ ] Nginx config validated: nginx -t (no errors)
    [ ] Nginx reloaded: docker exec pandya-nginx nginx -s reload
    [ ] curl http://localhost/ml/health returns 200 (through Nginx)
    [ ] curl http://localhost/ml/{endpoint} returns correct response

[ ] Infrastructure Dependencies
    [ ] PostgreSQL service started and healthy
    [ ] MinIO service started and healthy
    [ ] Redis service started and healthy
    [ ] MLflow service started and healthy
    [ ] All services reachable from project container (same network)

[ ] Database Connectivity
    [ ] Project connects to postgres at {domain}-postgres:5432
    [ ] Connection pooling configured (min_size=2, max_size=10)
    [ ] Migration scripts run cleanly (alembic upgrade head or equivalent)
    [ ] Tables created successfully (verify with psql)

[ ] Object Storage
    [ ] Project connects to MinIO at {domain}-minio:9000
    [ ] Bucket created (make s3-bootstrap or setup script)
    [ ] Test file uploads/downloads work
    [ ] No hardcoded AWS credentials (uses MinIO credentials from env)

[ ] Cache
    [ ] Project connects to Redis at {domain}-redis:6379
    [ ] Cache operations work (set/get)
    [ ] TTL settings configured correctly

[ ] Observability
    [ ] Logs visible in docker logs {project}
    [ ] Logs include request_id for tracing
    [ ] Metrics endpoint exists (if applicable): GET /metrics (Prometheus format)
    [ ] Grafana dashboard created per domain (shows project health, latency, errors)

[ ] End-to-End Testing
    [ ] E2E test file exists: tests/e2e/test_integration.py
    [ ] E2E tests run against live services (not mocks)
    [ ] E2E tests include: test_health, test_predict, test_database, test_s3
    [ ] E2E tests pass: make test-e2e
    [ ] Test reports include: pass/fail, latency, error details

[ ] Load Testing
    [ ] Load test defined: tests/load/locustfile.py (or wrk script)
    [ ] Load test runs cleanly: locust -f tests/load/locustfile.py
    [ ] Project handles 10 concurrent requests without error
    [ ] Response time under 500ms at p95
    [ ] No memory leaks (docker stats shows stable memory)

[ ] Failure Scenarios
    [ ] Test: Database connection lost → project returns 503
    [ ] Test: MinIO down → project returns 503
    [ ] Test: Redis down → project degrades gracefully (returns 200 with warning)
    [ ] Test: Nginx upstream removed → Nginx returns 502, auto-recovery when service up
    [ ] Recovery: Service restarts automatically (restart: unless-stopped)

[ ] Documentation
    [ ] docs/runbooks/{project}.md exists
    [ ] Runbook includes: how to run, how to debug, common issues, who to contact
    [ ] Runbook covers: deploy, monitor, troubleshoot, rollback
    [ ] Architecture diagram included (presentation-logic → application-logic → db-logic)

[ ] Git and CI/CD
    [ ] All code committed to git (no uncommitted changes)
    [ ] Latest commit has meaningful message (not "WIP" or "test")
    [ ] Git tags created: v1.0.0-beta (first deployment)
    [ ] CI/CD pipeline runs on push (if applicable)
    [ ] CI/CD passes: lint, test, build, security scan

[ ] Security
    [ ] No secrets in code (all from environment)
    [ ] No SQL injection vulnerabilities (use parameterized queries)
    [ ] No hardcoded API keys or passwords
    [ ] Security audit passed: bandit scan clean
    [ ] HTTPS/TLS enforced in Nginx (no unencrypted traffic from internet)

[ ] Monitoring and Alerts
    [ ] Grafana dashboard shows: request count, latency, error rate, CPU, memory
    [ ] Alerts configured: if error_rate > 5% or latency_p95 > 1000ms
    [ ] Alert notifications sent (email, Slack, etc., if configured)
    [ ] Dashboard updated daily with live metrics
```

**Verification:** Developer + Operations runs:
```bash
# Terminal 1: Start stack
docker-compose -f deployment/ml/docker-compose.yml up -d

# Terminal 2: Run tests
cd ml/ml-iris-knn
make test-e2e           # end-to-end tests
make test-load          # load test (5 min, 10 concurrent)

# Terminal 3: Verify Nginx routing
curl http://localhost/health           # Nginx health
curl http://localhost/ml/health        # Project health through Nginx
curl http://localhost/ml/predict -X POST -d '{"data": [1, 2, 3]}'  # Real request

# Check infrastructure
docker ps | grep ml-
docker logs ml-postgres | tail -20
docker logs ml-minio | tail -20
docker logs ml-redis | tail -20
docker logs ml-mlflow | tail -20

# Check metrics
open http://localhost:3000            # Grafana dashboard
```

**Owner:** Developer + DevOps  
**Timeline:** ~2-3 hours per project (includes load testing wait time)

---

## Readiness Checklist Document

Each project completion logged in `/docs/project-readiness-checklist.md`:

```markdown
# Project Readiness Checklist

## ML Domain

### ml-iris-knn
- [x] TIER 1 (Code Readiness) — May 5, 2026, Archit Pandya
- [x] TIER 2 (Docker Readiness) — May 5, 2026, Archit Pandya
- [ ] TIER 3 (Integration Readiness) — (pending)
- Status: TIER 2 COMPLETE, ready for TIER 3

### ml-housing
- [ ] TIER 1 (Code Readiness)
- [ ] TIER 2 (Docker Readiness)
- [ ] TIER 3 (Integration Readiness)
- Status: NOT STARTED

## DL Domain

### dl-lstm-forecast
- [ ] TIER 1, TIER 2, TIER 3
- Status: NOT STARTED

### dl-cnn-vision
- [ ] TIER 1, TIER 2, TIER 3
- Status: NOT STARTED

## NLP Domain

### nlp-sentiment-classifier
- [ ] TIER 1, TIER 2, TIER 3
- Status: NOT STARTED

### nlp-ner-tagger
- [ ] TIER 1, TIER 2, TIER 3
- Status: NOT STARTED

## Agentic Domain

### agentic-task-planner
- [ ] TIER 1, TIER 2, TIER 3
- Status: NOT STARTED

### agentic-o1-reasoner
- [ ] TIER 1, TIER 2, TIER 3
- Status: NOT STARTED
```

## Phase Gates

| Phase | Entry Criteria | Exit Criteria | Owner | Duration |
|---|---|---|---|---|
| **Phase 1a** | V3 structure applied, templates created | ml-iris-knn TIER 3 complete | Developer | ~1 week |
| **Phase 1b** | ml-iris-knn live, Nginx routing works | ml-housing TIER 3 complete | Developer | ~1 week |
| **Phase 2** | ML domain stable, 2 projects live | dl-lstm-forecast TIER 3 complete | Developer | ~2 weeks |
| **Phase 3** | DL domain stable | nlp-sentiment TIER 3 complete | Developer | ~2 weeks |
| **Phase 4** | NLP domain stable | agentic-planner TIER 3 complete | Developer | ~2 weeks |
| **Phase 5** | All 8 projects on NAS | Staging deployment plan approved | Developer | ~1 week |
| **Phase 6** | NAS production stable | AWS mirrored, live traffic on AWS | Developer + DevOps | ~3 weeks |

---

## Automation Opportunities

- **TIER 1 automated:** CI/CD runs `make lint`, `make test-unit`, `pip check`
- **TIER 2 partially automated:** CI/CD builds Docker image, scans for vulnerabilities
- **TIER 3 manual:** End-to-end tests and Nginx integration require live environment

---

## Related ADRs

- **ADR-014** — Project autonomy and templates (templates include all test fixtures, configs)
- **ADR-013** — Per-project 3-layer architecture (TIER 1 verifies structure)
- **ADR-019** — Internet access and domain routing (TIER 3 verifies Nginx integration)

---

**Status: READY FOR IMPLEMENTATION**

Readiness criteria locked. First project (ml-iris-knn) will be first to complete all three tiers.
