# Proxy Service

Nginx reverse proxy and trust boundary enforcement for pandyaHomeLab platform.

**Purpose:** Route incoming requests to backend services (MLflow, Grafana, MinIO, demos) based on path patterns per ADR-005. Enforce LAN-only access for operational UIs per ADR-012.

**Related ADRs:**
- ADR-005: Path-based routing
- ADR-006: Nginx replaces DSM proxy
- ADR-011: Per-service conventions
- ADR-012: Authentication strategy

**Health check:** GET /health returns 200 "ok"
