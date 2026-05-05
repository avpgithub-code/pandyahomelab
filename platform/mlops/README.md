# MLOps Tier

MLflow experiment tracking, model registry, and artifact management for pandyaHomeLab.

**Service:**
- **MLflow Server** — Web UI at port 5000; REST API for experiment tracking, model management, batch prediction

**Configuration:**
- Backend: SQLite (dev-nas) or PostgreSQL (prod-nas, uses data service)
- Artifact store: MinIO S3-compatible (uses data service)
- Health check: GET /health

**Volumes:** Persistent MLflow data at `./data/mlflow/`

**Related ADRs:**
- ADR-010: Secrets management (AWS credentials for MinIO)
- ADR-011: Per-service conventions

**Next phase:** Prometheus, Grafana, Loki (observability) added after MLflow stable.
