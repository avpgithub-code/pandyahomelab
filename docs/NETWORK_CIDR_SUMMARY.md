# pandyaHomeLab Network CIDR Summary

**Generated:** May 5, 2026  
**Last amended:** September 23, 2026 — [ADR-016 Amendment 1](adr/ADR-016-domain-level-network-topology.md#amendment-1--2026-09-23-host-ports-nginx-legs-platform-range)  
**Status:** LOCKED — changes go through an ADR-016 amendment  

> **Amendment 1 (2026-09-23)** reconciled this document with the running system: added the
> NAS host-port scheme (§8), the Nginx per-domain leg at `.20`, the platform-services range
> `.30–.39`, cloudflared, and the real container names. Network CIDRs and the `.1–.19`
> in-network scheme are **unchanged**.

---

## 1. NAS Level Networks (Synology Docker)

| Network Name | Docker name (compose project prefix) | CIDR Block | Gateway | Purpose | Status |
|---|---|---|---|---|---|
| pandya-proxy-network | `nginx_pandya-proxy-network` | 172.24.0.0/24 | 172.24.0.1 | Nginx reverse proxy entry point | Live |
| ml-network | `ml_ml-network` | 172.20.0.0/24 | 172.20.0.1 | ML domain services | Live (Phase 1) |
| dl-network | `dl_dl-network` | 172.21.0.0/24 | 172.21.0.1 | DL domain services | Live (Phase 2) |
| nlp-network | `nlp_nlp-network` | 172.22.0.0/24 | 172.22.0.1 | NLP domain services | Active (Phase 3.0, 2026-09-24) |
| agentic-network | `agentic_agentic-network` | 172.23.0.0/24 | 172.23.0.1 | Agentic AI domain services | Reserved (Phase 4) |

All bridge driver, local scope. The Docker name is what `external:` references in
`deployment/nginx/docker-compose.yml`; it comes from the stack living in `deployment/<domain>/`.

---

## 2. AWS Level Networks (VPC Architecture)

| Network Name | CIDR Block | Availability | Purpose | Type | Routing |
|---|---|---|---|---|---|
| VPC | 10.0.0.0/16 | us-east-1 | Main VPC for platform | VPC | N/A |
| Public Subnet | 10.0.100.0/24 | us-east-1a | ALB, NAT Gateway | Public | IGW |
| ml-subnet | 10.0.1.0/24 | us-east-1a/1b | ML ECS tasks | Private | NAT |
| dl-subnet | 10.0.2.0/24 | us-east-1a/1b | DL ECS tasks | Private | NAT |
| nlp-subnet | 10.0.3.0/24 | us-east-1a/1b | NLP ECS tasks | Private | NAT |
| agentic-subnet | 10.0.4.0/24 | us-east-1a/1b | Agentic ECS tasks | Private | NAT |

---

## 3. NAS ML Domain — Service IP Assignments (live)

| Service | Container Name | IP Address | Container Port | Host Port (§8) | Role |
|---|---|---|---|---|---|
| PostgreSQL | ml-postgres | 172.20.0.2 | 5432 | 127.0.0.1:5433 | Database |
| MinIO | ml-minio | 172.20.0.3 | 9000 / 9001 | 127.0.0.1:9000 / 0.0.0.0:9001 ⚠ | Artifact Storage |
| Redis | ml-redis | 172.20.0.4 | 6379 | 127.0.0.1:6379 | Cache |
| MLflow | ml-mlflow | 172.20.0.5 | 5000 | 0.0.0.0:5000 ⚠ | Experiment Tracking |
| Iris-KNN | ml-iris-knn | 172.20.0.10 | 8000 | 127.0.0.1:8001 | Project Service |
| Housing | ml-housing-linear | 172.20.0.11 | 8000 | 127.0.0.1:8002 | Project Service |
| Titanic AutoML | ml-titanic-automl | 172.20.0.12 | 8000 | 127.0.0.1:8003 | Project Service |
| Nginx (ML leg) | pandya-nginx | 172.20.0.20 | — | — | Reverse-proxy attachment |
| Analytics ingester | analytics-ingester | 172.20.0.30 | — | none | Platform service |
| Admin portal | admin-portal | 172.20.0.31 | — | none | Platform service |

⚠ = bound to all interfaces, not NAS-only. See §8 "Open item".

---

## 4. NAS DL Domain — Service IP Assignments (live)

| Service | Container Name | IP Address | Container Port | Host Port (§8) | Role |
|---|---|---|---|---|---|
| PostgreSQL | dl-postgres | 172.21.0.2 | 5432 | 127.0.0.1:5434 | Database |
| MinIO | dl-minio | 172.21.0.3 | 9000 / 9001 | 127.0.0.1:9002 / 0.0.0.0:9003 ⚠ | Artifact Storage |
| Redis | dl-redis | 172.21.0.4 | 6379 | 127.0.0.1:6380 | Cache |
| MLflow | dl-mlflow | 172.21.0.5 | 5000 | none (public via `mlflow-dl.` subdomain) | Experiment Tracking |
| MNIST CNN | dl-mnist-cnn | 172.21.0.10 | 8000 | 127.0.0.1:8010 | Project Service |
| LSTM Forecast | dl-lstm-forecast | 172.21.0.11 | 8000 | 127.0.0.1:8011 | Project Service |
| YOLO Object Detection | dl-yolo-object-detection | 172.21.0.12 | 8000 | 127.0.0.1:8012 | Reserved (Phase 2c) |
| Nginx (DL leg) | pandya-nginx | 172.21.0.20 | — | — | Reverse-proxy attachment |

---

## 5. NAS NLP Domain — Service IP Assignments (Phase 3; nlp-mlflow + Nginx leg live 2026-09-24)

| Service | Container Name | IP Address | Container Port | Host Port (§8) | Role |
|---|---|---|---|---|---|
| PostgreSQL | nlp-postgres | 172.22.0.2 | 5432 | 127.0.0.1:5435 | Database — reserved, not deployed (G1) |
| MinIO | nlp-minio | 172.22.0.3 | 9000 / 9001 | 127.0.0.1:9004 / 127.0.0.1:9005 | Artifact Storage — reserved, not deployed (G1) |
| Redis | nlp-redis | 172.22.0.4 | 6379 | 127.0.0.1:6381 | Cache — reserved, not deployed (G1) |
| MLflow | nlp-mlflow | 172.22.0.5 | 5000 | none (public via `mlflow-nlp.` subdomain) | Experiment Tracking — ✅ live |
| Quora duplicate questions | nlp-quora-randomforest | 172.22.0.10 | 8000 | 127.0.0.1:8020 | Project Service (Phase 3a) |
| Text representation lab | nlp-imdb-textrep | 172.22.0.11 | 8000 | 127.0.0.1:8021 | Project Service (Phase 3b) |
| Project slot | nlp-<dataset-algorithm> | 172.22.0.12 | 8000 | 127.0.0.1:8022 | Reserved (Phase 3c) |
| Project slot | nlp-<dataset-algorithm> | 172.22.0.13 | 8000 | 127.0.0.1:8023 | Reserved (Phase 3d) |
| Nginx (NLP leg) | pandya-nginx | 172.22.0.20 | — | — | Reverse-proxy attachment |

Phase 3 deploys **nlp-mlflow only** (Phase 3 gate G1, ADR-016 Amendment 1). The postgres/minio/redis
slots stay reserved and are brought up only when a demo actually uses one.
Container names follow [ADR-004](adr/ADR-004-demo-naming-convention.md) (`dataset-algorithm`).
Slot names for 3b–3d are set at each sub-phase decision gate. See
[PHASE_3_MASTER_PLAN.md](PHASE_3_MASTER_PLAN.md).

---

## 6. NAS Agentic Domain — Service IP Assignments (reserved, Phase 4)

| Service | Container Name | IP Address | Container Port | Host Port (§8) | Role |
|---|---|---|---|---|---|
| PostgreSQL | agentic-postgres | 172.23.0.2 | 5432 | 127.0.0.1:5436 | Database |
| MinIO | agentic-minio | 172.23.0.3 | 9000 / 9001 | 127.0.0.1:9006 / 127.0.0.1:9007 | Artifact Storage |
| Redis | agentic-redis | 172.23.0.4 | 6379 | 127.0.0.1:6382 | Cache |
| MLflow | agentic-mlflow | 172.23.0.5 | 5000 | none (public via `mlflow-agentic.` subdomain) | Experiment Tracking |
| Project slots | agentic-<dataset-algorithm> | 172.23.0.10–.19 | 8000 | 127.0.0.1:8030–8039 | Reserved (e.g. `agentic-pandyalab-docs-rag`) |
| Nginx (Agentic leg) | pandya-nginx | 172.23.0.20 | — | — | Reverse-proxy attachment |

---

## 7. NAS Proxy Network — Entry Point

| Service | Container Name | IP Address | Container Port | Host Port | Role |
|---|---|---|---|---|---|
| Nginx Reverse Proxy | pandya-nginx | 172.24.0.2 | 80 / 443 | 8080 / 8443 | Entry point (public traffic arrives via cloudflared) |
| Cloudflare Tunnel | pandya-cloudflared | 172.24.0.3 | — | none | Outbound tunnel → `https://pandya-nginx:443` |

Nginx is multi-homed. It has one interface on the proxy network plus one leg per live domain
network, always at **`.20`** of that domain's /24. A domain leg is added to
`deployment/nginx/docker-compose.yml` **only after** that domain's network and upstream
containers exist, because Nginx resolves upstreams eagerly at startup.

---

## 8. NAS Host Port Allocation

Every published host port is bound to `127.0.0.1` (NAS-only) unless noted otherwise. Public traffic
never uses these ports. It goes cloudflared → Nginx → the domain network IP. Host ports are for
on-NAS debugging (`curl localhost:80xx/health`) only.

| Port family | ML | DL | NLP | Agentic | Rule |
|---|---|---|---|---|---|
| Project services (container 8000) | 8001–8009 | 8010–8019 | **8020–8029** | 8030–8039 | One block of ten per domain; slot `.1N` → `80` + domain index + `N` (DL `.10`→8010, NLP `.10`→8020). ML is off by one (`.10`→8001), legacy |
| PostgreSQL (5432) | 5433 | 5434 | **5435** | 5436 | 5433 + domain index |
| MinIO API / console (9000 / 9001) | 9000 / 9001 | 9002 / 9003 | **9004 / 9005** | 9006 / 9007 | +2 per domain |
| Redis (6379) | 6379 | 6380 | **6381** | 6382 | 6379 + domain index |
| MLflow (5000) | 5000 (legacy) | none | **none** | none | New domains publish MLflow only via `mlflow-<domain>.pandyahomelab.com` |
| Nginx (80 / 443) | — | — | — | — | 8080 / 8443, shared entry point (§7) |
| Platform services (.30–.39) | none | — | — | — | Not published to the host |

Domain index: ML = 0, DL = 1, NLP = 2, Agentic = 3. ML's 8001–8003 predates the rule and keeps
its numbers.

**Open item (not changed by Amendment 1):** `ml-mlflow:5000`, `ml-minio:9001` and
`dl-minio:9003` are still bound to `0.0.0.0` (reachable on the NAS LAN). Everything else was
moved to `127.0.0.1` in the 2026-09-23 hardening pass. New domains (NLP, Agentic) bind **all**
host ports to `127.0.0.1`, including the MinIO console. Whether to tighten ML/DL is a separate
decision.

---

## 9. AWS ECS Task Assignments (Phase 6)

| Task Name | Subnet | IP Range | Count | CPU | Memory | Role |
|---|---|---|---|---|---|---|
| ml-iris-knn | ml-subnet (10.0.1.0/24) | 10.0.1.x | 2-4 | 256 units | 512 MB | ML Service |
| ml-housing-linear | ml-subnet (10.0.1.0/24) | 10.0.1.x | 1-2 | 256 units | 512 MB | ML Service |
| dl-mnist-cnn | dl-subnet (10.0.2.0/24) | 10.0.2.x | 1-2 | 512 units | 1024 MB | DL Service |
| dl-lstm-forecast | dl-subnet (10.0.2.0/24) | 10.0.2.x | 1-2 | 512 units | 1024 MB | DL Service |
| nlp-quora-randomforest | nlp-subnet (10.0.3.0/24) | 10.0.3.x | 1-2 | 256 units | 512 MB | NLP Service |
| agentic-* | agentic-subnet (10.0.4.0/24) | 10.0.4.x | 1-2 | 512 units | 1024 MB | Agentic Service |

---

## 10. AWS Managed Services (Phase 6)

| Service | Type | Subnet/Scope | CIDR/Region | Purpose |
|---|---|---|---|---|
| RDS PostgreSQL (ml) | Database | ml-subnet (private) | 10.0.1.0/24 | ML domain database |
| RDS PostgreSQL (dl) | Database | dl-subnet (private) | 10.0.2.0/24 | DL domain database |
| RDS PostgreSQL (nlp) | Database | nlp-subnet (private) | 10.0.3.0/24 | NLP domain database |
| RDS PostgreSQL (agentic) | Database | agentic-subnet (private) | 10.0.4.0/24 | Agentic domain database |
| S3 Bucket (ml-artifacts) | Object Storage | us-east-1 | N/A | ML artifact storage |
| S3 Bucket (dl-artifacts) | Object Storage | us-east-1 | N/A | DL artifact storage |
| S3 Bucket (nlp-artifacts) | Object Storage | us-east-1 | N/A | NLP artifact storage |
| S3 Bucket (agentic-artifacts) | Object Storage | us-east-1 | N/A | Agentic artifact storage |
| ElastiCache Redis (ml) | Cache | ml-subnet (private) | 10.0.1.0/24 | ML caching |
| ElastiCache Redis (dl) | Cache | dl-subnet (private) | 10.0.2.0/24 | DL caching |
| ElastiCache Redis (nlp) | Cache | nlp-subnet (private) | 10.0.3.0/24 | NLP caching |
| ElastiCache Redis (agentic) | Cache | agentic-subnet (private) | 10.0.4.0/24 | Agentic caching |

---

## 11. CIDR Range Summary & Conflict Analysis

| Range | Usage | Status | Conflicts | Notes |
|---|---|---|---|---|
| 172.17.0.0/16 | Docker default bridge | In Use | None | Already in use, DO NOT use |
| 172.18.0.0/16 | Available | Available | None | Can use if needed in future |
| 172.19.0.0/16 | Available | Available | None | Can use if needed in future |
| 172.20.0.0/24 | ml-network (NAS) | Live | None | ✅ Verified live 2026-09-23 |
| 172.21.0.0/24 | dl-network (NAS) | Live | None | ✅ Verified live 2026-09-23 |
| 172.22.0.0/24 | nlp-network (NAS) | Allocated | None | ✅ Not in use by any Docker network (2026-09-23) |
| 172.23.0.0/24 | agentic-network (NAS) | Allocated | None | ✅ Not in use by any Docker network (2026-09-23) |
| 172.24.0.0/24 | pandya-proxy-network (NAS) | Live | None | ✅ Verified live 2026-09-23 |
| 192.168.x.x | Synology NAS Management | In Use | None | NAS LAN, no Docker conflict |
| 10.0.0.0/16 | AWS VPC | Allocated | None | ✅ AWS standard, no NAS conflict |
| 10.0.1.0/24 | ml-subnet (AWS) | Allocated | None | ✅ Safe for AWS |
| 10.0.2.0/24 | dl-subnet (AWS) | Allocated | None | ✅ Safe for AWS |
| 10.0.3.0/24 | nlp-subnet (AWS) | Allocated | None | ✅ Safe for AWS |
| 10.0.4.0/24 | agentic-subnet (AWS) | Allocated | None | ✅ Safe for AWS |
| 10.0.100.0/24 | Public subnet (AWS) | Allocated | None | ✅ ALB, NAT Gateway |

---

## 12. Network Isolation Matrix (NAS)

| From → To | ml-network | dl-network | nlp-network | agentic-network | pandya-proxy-network | External |
|---|---|---|---|---|---|---|
| ml-network | ✅ Direct | ❌ Via Nginx | ❌ Via Nginx | ❌ Via Nginx | ✅ Reverse Proxy | ✅ Via Nginx |
| dl-network | ❌ Via Nginx | ✅ Direct | ❌ Via Nginx | ❌ Via Nginx | ✅ Reverse Proxy | ✅ Via Nginx |
| nlp-network | ❌ Via Nginx | ❌ Via Nginx | ✅ Direct | ❌ Via Nginx | ✅ Reverse Proxy | ✅ Via Nginx |
| agentic-network | ❌ Via Nginx | ❌ Via Nginx | ❌ Via Nginx | ✅ Direct | ✅ Reverse Proxy | ✅ Via Nginx |
| pandya-proxy-network | ✅ Upstream | ✅ Upstream | ✅ Upstream | ✅ Upstream | ✅ Direct | ✅ Via cloudflared |
| External | ❌ No direct | ❌ No direct | ❌ No direct | ❌ No direct | ✅ Via Cloudflare Tunnel | N/A |

---

## 13. Docker Compose IPAM Configuration Template

```yaml
# deployment/nlp/docker-compose.yml  (base: network + domain infra)
networks:
  nlp-network:
    driver: bridge
    ipam:
      driver: default
      config:
        - subnet: 172.22.0.0/24
          gateway: 172.22.0.1

services:
  nlp-postgres:
    ports: ["127.0.0.1:5435:5432"]
    networks:
      nlp-network:
        ipv4_address: 172.22.0.2

  nlp-minio:
    ports: ["127.0.0.1:9004:9000", "127.0.0.1:9005:9001"]
    networks:
      nlp-network:
        ipv4_address: 172.22.0.3

  nlp-redis:
    ports: ["127.0.0.1:6381:6379"]
    networks:
      nlp-network:
        ipv4_address: 172.22.0.4

  nlp-mlflow:            # no host port — public via mlflow-nlp.pandyahomelab.com
    networks:
      nlp-network:
        ipv4_address: 172.22.0.5

# deployment/nlp/docker-compose.dev.yml  (overlay: project services)
  nlp-quora-randomforest:
    ports: ["127.0.0.1:8020:8000"]
    networks:
      nlp-network:
        ipv4_address: 172.22.0.10

# deployment/nginx/docker-compose.yml  (add ONLY after the above is up)
#   networks:  nlp_nlp-network: { external: true }
#   pandya-nginx.networks.nlp_nlp-network.ipv4_address: 172.22.0.20
```

---

## 14. Migration Path: NAS → AWS

| Phase | Environment | CIDR Range | Services | Status |
|---|---|---|---|---|
| Phase 1-5 | NAS (Synology Docker) | 172.20-24/24 | All 4 domains | Development |
| Phase 6 Early | NAS (stays online) | 172.20-24/24 | Fallback/dev copy | Parallel |
| Phase 6 Middle | AWS (new deployment) | 10.0.x/24 | All 4 domains | Staging |
| Phase 6 Late | AWS (production) | 10.0.x/24 | All 4 domains | Production |
| Phase 6 Final | NAS (dev only) | 172.20-24/24 | Reduced workload | Dev/Fallback |

---

## 15. DNS & Routing Summary

| Environment | Hostname / Path | Entry Point | Target | IP/Port |
|---|---|---|---|---|
| NAS | pandyahomelab.com | Cloudflare Tunnel → Nginx | pandya-nginx | 172.24.0.2:443 (host 8443) |
| NAS | /ml/* | Nginx upstream | ml-* project services | 172.20.0.10–.19:8000 |
| NAS | /dl/* | Nginx upstream | dl-* project services | 172.21.0.10–.19:8000 |
| NAS | /nlp/<name>/ (flat, G2) | Nginx upstream | nlp-* project services | 172.22.0.10–.19:8000 |
| NAS | /agentic/* | Nginx upstream | agentic-* project services | 172.23.0.10–.19:8000 |
| NAS | mlflow-dl.pandyahomelab.com | Tunnel ingress → Nginx `server` block | dl-mlflow | 172.21.0.5:5000 |
| NAS | mlflow-nlp.pandyahomelab.com | Tunnel ingress → Nginx `server` block | nlp-mlflow | 172.22.0.5:5000 ✅ live (read-only) |
| AWS | pandyahomelab.com | ALB | ALB DNS | ALB IP |
| AWS | /ml/* · /dl/* · /nlp/* · /agentic/* | ALB target groups | ECS services | 10.0.{1-4}.x:8000 |

---

## 16. Quick Reference: IP Address Allocation Scheme

```
NAS DOCKER NETWORKS — identical layout in every domain /24:
  .1        = Gateway
  .2        = PostgreSQL
  .3        = MinIO
  .4        = Redis
  .5        = MLflow
  .10-.19   = Project services
  .20       = Nginx leg (pandya-nginx second/third/... interface)
  .30-.39   = Platform services (only ML today: .30 analytics-ingester, .31 admin-portal)

172.20.0.x  ML       (domain index 0) host ports 8001-8009, 5433, 9000/9001, 6379
172.21.0.x  DL       (domain index 1) host ports 8010-8019, 5434, 9002/9003, 6380
172.22.0.x  NLP      (domain index 2) host ports 8020-8029, 5435, 9004/9005, 6381
172.23.0.x  Agentic  (domain index 3) host ports 8030-8039, 5436, 9006/9007, 6382

172.24.0.x  Proxy
  .1 = Gateway
  .2 = Nginx (host 8080/8443)
  .3 = cloudflared

AWS VPC SUBNETS:
10.0.1.x      - ml-subnet (private)
10.0.2.x      - dl-subnet (private)
10.0.3.x      - nlp-subnet (private)
10.0.4.x      - agentic-subnet (private)
10.0.100.x    - Public subnet (ALB, NAT)
```

---

## 17. Verification Checklist

- [x] NAS Docker networks verified (172.17.0.0/16 is only Docker default in use)
- [x] No conflicts with Synology management network (192.168.x.x)
- [x] AWS VPC CIDR (10.0.0.0/16) doesn't conflict with NAS (172.x.x.x)
- [x] Site-to-site VPN possible between NAS and AWS (different ranges)
- [x] Each domain has isolated network (no cross-network direct access)
- [x] Nginx is sole entry point from internet (via Cloudflare Tunnel)
- [x] All infrastructure services (postgres, minio, redis, mlflow) isolated per domain
- [x] Project services can only reach other services via Nginx routing
- [x] 2026-09-23: §3/§4/§7 match `docker inspect` of every running container; NLP/Agentic IPs and §8 host ports are unused
- [x] 2026-09-24: nlp_nlp-network = 172.22.0.0/24 (gw .1); nlp-mlflow = 172.22.0.5, no host port; pandya-nginx = 172.22.0.20

---

**Status: LOCKED** ✅ — amend via ADR-016.
