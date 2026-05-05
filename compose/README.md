# Platform Composition

Central orchestration for pandyaHomeLab platform services.

**Services orchestrated:**
- **Proxy** (Nginx) — reverse proxy, trust boundary
- **PostgreSQL** — relational data backend
- **MinIO** — artifact and dataset storage
- **Redis** — caching and sessions
- **MLflow** — experiment tracking and model registry
- **Grafana** — monitoring and dashboards (placeholder for observability)

**How to run (dev-nas):**
```bash
cp .env.example .env
# Edit .env with your passwords
docker-compose up -d
```

**Ports:**
- Proxy: 80, 443
- PostgreSQL: 5432
- MinIO: 9000 (API), 9001 (console)
- Redis: 6379
- MLflow: 5000
- Grafana: 3000

**Network:** All services on `pandya-platform` bridge network per ADR-007.

**Related ADRs:**
- ADR-007: Repository layout
- ADR-009: Filesystem and permissions
- ADR-010: Secrets management
- ADR-011: Per-service conventions
