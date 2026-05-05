---
title: Domain-Level Network Topology & Infrastructure
status: Proposed (new)
context: |
  V3 architecture establishes 4 independent domains (ML, DL, NLP, Agentic) each with isolated
  infrastructure. Network topology must support:
  
  1. Complete domain isolation (no direct cross-domain communication)
  2. Scalable migration from NAS (172.x.x.x) to AWS (10.x.x.x)
  3. Public entry point (Nginx) with private service networks
  4. Resource efficiency on Synology NAS (16GB, 4-core)
  5. Parity between NAS and AWS layers (same pattern, different CIDR ranges)
decision: |
  Establish domain-isolated Docker networks on NAS and subnets on AWS per the allocation scheme
  below. Each domain receives dedicated infrastructure (PostgreSQL, MinIO, Redis, MLflow) with
  no cross-network communication except through Nginx reverse proxy.
  
  NAS LAYER (Synology Docker):
  - ml-network:       172.20.0.0/24  (gateway: 172.20.0.1)
  - dl-network:       172.21.0.0/24  (gateway: 172.21.0.1)
  - nlp-network:      172.22.0.0/24  (gateway: 172.22.0.1)
  - agentic-network:  172.23.0.0/24  (gateway: 172.23.0.1)
  - pandya-proxy-network: 172.24.0.0/24 (gateway: 172.24.0.1, Nginx only)
  
  AWS LAYER (VPC):
  - VPC CIDR:         10.0.0.0/16
  - Public subnet:    10.0.100.0/24 (ALB, NAT Gateway)
  - ml-subnet:        10.0.1.0/24 (private, ECS tasks)
  - dl-subnet:        10.0.2.0/24 (private, ECS tasks)
  - nlp-subnet:       10.0.3.0/24 (private, ECS tasks)
  - agentic-subnet:   10.0.4.0/24 (private, ECS tasks)
  
  Within each domain network (NAS), IP allocation follows consistent pattern:
  - .1 = Gateway
  - .2 = PostgreSQL
  - .3 = MinIO
  - .4 = Redis
  - .5 = MLflow
  - .10-.19 = Project services (e.g., ml-iris-knn at 172.20.0.10)
  
  All external traffic enters via Nginx on pandya-proxy-network (exposed ports 80/443).
  Domain services remain on private networks, reachable only through Nginx upstreams.
alternatives_considered: |
  A. Flat network (all services on one network) — rejected, no domain isolation, security risk
  B. Shared infrastructure per domain (one postgres, one minio shared by 2 projects) — rejected,
     violates project autonomy, creates coupling
  C. Domain-isolated networks with cross-network direct routes — rejected, violates isolation
  D. Domain-isolated networks, all cross-domain via Nginx (chosen) — ensures isolation, supports
     future network segmentation, scales cleanly to AWS with subnet architecture
consequences: |
  Positive:
  - Complete domain isolation (security boundary per domain)
  - Resource efficiency (one postgres, one minio, one redis per domain, shared by 2 projects)
  - Clear migration path to AWS (NAS pattern identical, just different CIDR ranges)
  - Supports site-to-site VPN between NAS and AWS (no overlapping ranges)
  - Each domain can be taken offline independently for maintenance
  - Future API gateway can enforce per-domain rate limiting/auth
  
  Negative:
  - Domain-level data consistency harder (no cross-domain transactions)
  - Troubleshooting cross-domain issues requires understanding Nginx routing
  
  Mitigations:
  - Nginx access logs document all cross-domain requests
  - ADR-019 (Internet Access & Domain Routing) specifies routing rules
  - Per-domain dashboards in Grafana for visibility
related_adrs: |
  - ADR-013 — Per-project 3-layer architecture (projects run within domain networks)
  - ADR-015 — Deployment service separation (docker-compose files implement this topology)
  - ADR-019 — Internet Access from NAS & Domain Routing (Nginx configuration details)
  - ADR-007 (V3 revision) — Repository layout (domains at root level: ml/, dl/, nlp/, agentic/)
---

# ADR-016 — Domain-Level Network Topology & Infrastructure

**Status:** Proposed (new)  
**Date:** May 2026  
**Author:** Archit Pandya

## Context

V3 architecture establishes four independent AI domains (ML, DL, NLP, Agentic) as first-class citizens in the repository. Each domain runs autonomous infrastructure to support project isolation and scalability.

**Network requirements:**
1. Complete domain isolation (no accidental cross-domain data flow)
2. Scalable design that maps cleanly from NAS (development) to AWS (production)
3. Public entry point with private service networks (security by default)
4. Resource efficiency on Synology NAS (16GB RAM, 4-core CPU shared across all domains)
5. Support for iterative phased deployment (Phase 1-5 on NAS, Phase 6 mirror to AWS)

## Decision

Establish **domain-isolated Docker networks on NAS** and **domain-isolated subnets on AWS**, with Nginx as the sole public entry point.

### NAS Layer — Verified CIDR Allocation

```
ml-network       172.20.0.0/24  gateway: 172.20.0.1
dl-network       172.21.0.0/24  gateway: 172.21.0.1
nlp-network      172.22.0.0/24  gateway: 172.22.0.1
agentic-network  172.23.0.0/24  gateway: 172.23.0.1
pandya-proxy-network 172.24.0.0/24  gateway: 172.24.0.1
```

**Verification:** Synology Docker default network (172.17.0.0/16) is the only Docker network in use. 
Ranges 172.20-24 verified as available. No conflicts with Synology management network (192.168.x.x).

### AWS Layer — VPC Subnets (Phase 6+)

```
VPC              10.0.0.0/16
Public subnet    10.0.100.0/24  (ALB, NAT Gateway, us-east-1a)
ml-subnet        10.0.1.0/24    (private, us-east-1a/1b)
dl-subnet        10.0.2.0/24    (private, us-east-1a/1b)
nlp-subnet       10.0.3.0/24    (private, us-east-1a/1b)
agentic-subnet   10.0.4.0/24    (private, us-east-1a/1b)
```

**No CIDR overlap:** 172.20-24 (NAS) vs 10.0.x (AWS) allows future site-to-site VPN.

### Service IP Allocation — Within Each Domain Network

Consistent allocation pattern across all four domains:

```
.1  = Network gateway (assigned by Docker)
.2  = PostgreSQL
.3  = MinIO object storage
.4  = Redis cache
.5  = MLflow experiment tracking
.10-.19 = Project services (ml-iris-knn at .10, ml-housing at .11, etc.)
```

**Example (ML domain on NAS):**
```
172.20.0.1  - ml-network gateway
172.20.0.2  - ml-postgres
172.20.0.3  - ml-minio
172.20.0.4  - ml-redis
172.20.0.5  - ml-mlflow
172.20.0.10 - ml-iris-knn project
172.20.0.11 - ml-housing project
```

**Example (ML domain on AWS, ECS tasks):**
```
10.0.1.x (dynamic) - ml-iris-knn ECS tasks
10.0.1.x (dynamic) - ml-housing ECS tasks
```

### Traffic Flow — Public to Private

```
Internet traffic
    ↓ (HTTPS port 443)
Nginx (172.24.0.2, PUBLIC entry point)
    ↓ (HTTP upstream, internal)
Domain-specific service (e.g., 172.20.0.10 for ml-iris-knn)
    ↓ (internal)
PostgreSQL, MinIO, Redis (within domain network)
```

**Key invariant:** No service on private domain networks is reachable from internet.
Only Nginx ports 80/443 are exposed to host.

### Docker Compose IPAM Configuration

Each domain uses explicit IPAM to guarantee IP stability:

```yaml
# deployment/ml/docker-compose.yml
networks:
  ml-network:
    driver: bridge
    ipam:
      driver: default
      config:
        - subnet: 172.20.0.0/24
          gateway: 172.20.0.1

services:
  ml-postgres:
    networks:
      ml-network:
        ipv4_address: 172.20.0.2

  ml-minio:
    networks:
      ml-network:
        ipv4_address: 172.20.0.3

  ml-redis:
    networks:
      ml-network:
        ipv4_address: 172.20.0.4

  ml-mlflow:
    networks:
      ml-network:
        ipv4_address: 172.20.0.5

  ml-iris-knn:
    networks:
      ml-network:
        ipv4_address: 172.20.0.10

  ml-housing:
    networks:
      ml-network:
        ipv4_address: 172.20.0.11
```

Same pattern for dl-network (172.21.x), nlp-network (172.22.x), agentic-network (172.23.x).

### Network Isolation Matrix (NAS)

```
From → To          | ml-network | dl-network | nlp-network | agentic-network | proxy-network | External
ml-network         | ✅ Direct  | ❌ Via Nginx | ❌ Via Nginx | ❌ Via Nginx    | ✅ Proxy     | ✅ Via Nginx
dl-network         | ❌ Via Nginx | ✅ Direct  | ❌ Via Nginx | ❌ Via Nginx    | ✅ Proxy     | ✅ Via Nginx
nlp-network        | ❌ Via Nginx | ❌ Via Nginx | ✅ Direct  | ❌ Via Nginx    | ✅ Proxy     | ✅ Via Nginx
agentic-network    | ❌ Via Nginx | ❌ Via Nginx | ❌ Via Nginx | ✅ Direct      | ✅ Proxy     | ✅ Via Nginx
proxy-network      | ✅ Upstream | ✅ Upstream | ✅ Upstream | ✅ Upstream     | ✅ Direct    | ✅ Port 80/443
External           | ❌ No direct | ❌ No direct | ❌ No direct | ❌ No direct   | ✅ Exposed   | N/A
```

**Interpretation:**
- Intra-domain communication (ml-network → ml-network services) is direct
- Cross-domain communication (ml-network → dl-network) **must** route through Nginx
- External internet traffic **only** enters via Nginx (public entry point)

### Resource Allocation — NAS (16GB, 4-core)

Per domain (each domain shares infrastructure per the allocation above):
```
PostgreSQL: ~500MB RAM + 2GB disk (per domain)
MinIO:      ~300MB RAM + 5GB disk (per domain)
Redis:      ~100MB RAM (per domain)
MLflow:     ~200MB RAM (per domain)
Project services: ~1GB RAM combined (2 projects per domain)
Nginx:      ~50MB RAM
Grafana:    ~200MB RAM
```

**Total:** ~6GB RAM + 40GB storage for all infrastructure. Leaves 10GB for model storage and kernel.

## Alternatives Considered

### A. Single network for all services
**Rejected** — No domain isolation, cross-domain data flow possible, security risk, no clear scaling pattern.

### B. Per-project networks (8 networks total)
**Rejected** — Excessive fragmentation, hard to share infrastructure (each project needs own postgres), scales poorly.

### C. Domain-isolated networks with direct cross-domain routes
**Rejected** — Defeats isolation, violates architectural intent, makes network debugging harder.

### D. Domain-isolated networks, all cross-domain via Nginx (chosen)
**Accepted** — Clear boundaries, infrastructure sharing per domain, scales cleanly to AWS (subnets), supports future API gateway for auth/rate limiting.

## Consequences

### Positive
- **Complete domain isolation** — Each domain can be taken offline independently, security boundary enforced
- **Resource efficiency** — Infrastructure shared per domain, not per project (one postgres supports 2 projects)
- **Clear migration path** — NAS pattern (172.20-24) translates to AWS (10.0.1-4) with identical topology
- **Scales to AWS** — VPC subnets follow same pattern, Nginx becomes ALB, migration is structural not conceptual
- **Supports future API gateway** — Can add per-domain rate limiting, authentication, analytics
- **Debuggability** — Network logs show which domain cross-domain requests traverse, Nginx access logs are truth source

### Negative
- **Cross-domain data consistency** — No multi-domain transactions, each domain is independent data store
- **Routing complexity** — Developers must understand Nginx upstreams to debug cross-domain calls
- **Operational overhead** — 5 Docker networks to manage on NAS (4 domains + proxy), but minimal at current scale

### Mitigations
- **Documentation:** ADR-019 specifies all Nginx routing rules
- **Observability:** Grafana dashboards per domain, Nginx access logs for cross-domain tracing
- **Testing:** Integration tests verify Nginx routes correct requests to correct domains
- **CI/CD:** Compose validation ensures all upstream targets are healthy before serving traffic

## Implementation Notes

### For NAS (Phases 1-5)
1. Create separate `docker-compose.yml` per domain in `deployment/ml/`, `deployment/dl/`, etc.
2. Each compose file defines domain network with explicit IPAM (subnet + gateway)
3. Each compose file names services consistently: `{domain}-{service}` (e.g., ml-postgres, ml-minio)
4. Main compose orchestration file (`deployment/docker-compose.yml`) is empty or minimal; domains run independently
5. Nginx config upstream blocks reference internal IPs (172.20.0.10, 172.21.0.10, etc.)

### For AWS (Phase 6+)
1. Create VPC with CIDR 10.0.0.0/16
2. Create 6 subnets (1 public, 4 private per domain, plus public for ALB/NAT)
3. Create security groups per subnet (ingress from ALB only)
4. ECS tasks placed in corresponding domain subnet, auto-assigned IPs from pool
5. ALB target groups per domain upstream, point to ECS service discovery
6. Identical Nginx config, but ALB replaces self-hosted Nginx

## Related ADRs

- **ADR-013** — Per-project 3-layer architecture (projects run within these domain networks)
- **ADR-015** — Deployment service separation (docker-compose files implement this topology)
- **ADR-019** — Internet Access from NAS & Domain Routing (Nginx upstream configs, routing rules)
- **ADR-007** (V3 revision) — Repository layout (domains at root: ml/, dl/, nlp/, agentic/)

---

**Status: READY FOR IMPLEMENTATION**

All CIDR ranges verified, no conflicts detected, network isolation matrix validated.
Next step: ADR-019 (Nginx routing configuration), then Phase 1a execution.
