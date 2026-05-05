# Data Tier

PostgreSQL, MinIO, and Redis for pandyaHomeLab platform.

**Services:**
- **PostgreSQL 16** — relational database for experiment tracking (MLflow), demo state
- **MinIO** — S3-compatible object storage for model artifacts, datasets
- **Redis** — in-memory cache and session store

**Ports:**
- PostgreSQL: 5432
- MinIO API: 9000, Console: 9001
- Redis: 6379

**Volumes:** Per-container read-write to `/data/{postgres,minio,redis}/` per ADR-009

**Related ADRs:**
- ADR-009: Filesystem and permissions
- ADR-010: Secrets management
- ADR-011: Per-service conventions

**Health checks:** All services include health endpoints for compose orchestration.
