# pandyaHomeLab Network CIDR Summary

**Generated:** May 5, 2026  
**Status:** LOCKED - Ready for Implementation  

---

## 1. NAS Level Networks (Synology Docker)

| Network Name | CIDR Block | Gateway | Scope | Purpose | Driver |
|---|---|---|---|---|---|
| pandya-proxy-network | 172.24.0.0/24 | 172.24.0.1 | local | Nginx reverse proxy entry point | bridge |
| ml-network | 172.20.0.0/24 | 172.20.0.1 | local | ML domain services | bridge |
| dl-network | 172.21.0.0/24 | 172.21.0.1 | local | DL domain services | bridge |
| nlp-network | 172.22.0.0/24 | 172.22.0.1 | local | NLP domain services | bridge |
| agentic-network | 172.23.0.0/24 | 172.23.0.1 | local | Agentic AI domain services | bridge |

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

## 3. NAS ML Domain - Service IP Assignments

| Service Name | Container Name | IP Address | Port | Network | Role |
|---|---|---|---|---|---|
| PostgreSQL | ml-postgres | 172.20.0.2 | 5432 | ml-network | Database |
| MinIO | ml-minio | 172.20.0.3 | 9000/9001 | ml-network | Artifact Storage |
| Redis | ml-redis | 172.20.0.4 | 6379 | ml-network | Cache |
| MLflow | ml-mlflow | 172.20.0.5 | 5000 | ml-network | Experiment Tracking |
| Iris-KNN | ml-iris-knn | 172.20.0.10 | 8000 | ml-network | Project Service |
| Housing | ml-housing | 172.20.0.11 | 8000 | ml-network | Project Service |

---

## 4. NAS DL Domain - Service IP Assignments

| Service Name | Container Name | IP Address | Port | Network | Role |
|---|---|---|---|---|---|
| PostgreSQL | dl-postgres | 172.21.0.2 | 5432 | dl-network | Database |
| MinIO | dl-minio | 172.21.0.3 | 9000/9001 | dl-network | Artifact Storage |
| Redis | dl-redis | 172.21.0.4 | 6379 | dl-network | Cache |
| MLflow | dl-mlflow | 172.21.0.5 | 5000 | dl-network | Experiment Tracking |
| LSTM Forecast | dl-lstm | 172.21.0.10 | 8000 | dl-network | Project Service |
| CNN Vision | dl-cnn | 172.21.0.11 | 8000 | dl-network | Project Service |

---

## 5. NAS NLP Domain - Service IP Assignments

| Service Name | Container Name | IP Address | Port | Network | Role |
|---|---|---|---|---|---|
| PostgreSQL | nlp-postgres | 172.22.0.2 | 5432 | nlp-network | Database |
| MinIO | nlp-minio | 172.22.0.3 | 9000/9001 | nlp-network | Artifact Storage |
| Redis | nlp-redis | 172.22.0.4 | 6379 | nlp-network | Cache |
| MLflow | nlp-mlflow | 172.22.0.5 | 5000 | nlp-network | Experiment Tracking |
| Sentiment Analyzer | nlp-sentiment | 172.22.0.10 | 8000 | nlp-network | Project Service |
| NER Tagger | nlp-ner | 172.22.0.11 | 8000 | nlp-network | Project Service |

---

## 6. NAS Agentic Domain - Service IP Assignments

| Service Name | Container Name | IP Address | Port | Network | Role |
|---|---|---|---|---|---|
| PostgreSQL | agentic-postgres | 172.23.0.2 | 5432 | agentic-network | Database |
| MinIO | agentic-minio | 172.23.0.3 | 9000/9001 | agentic-network | Artifact Storage |
| Redis | agentic-redis | 172.23.0.4 | 6379 | agentic-network | Cache |
| MLflow | agentic-mlflow | 172.23.0.5 | 5000 | agentic-network | Experiment Tracking |
| Task Planner | agentic-planner | 172.23.0.10 | 8000 | agentic-network | Project Service |
| O1 Reasoner | agentic-o1 | 172.23.0.11 | 8000 | agentic-network | Project Service |

---

## 7. NAS Proxy Network - Nginx Entry Point

| Service Name | Container Name | IP Address | Port (Container) | Port (Host) | Network | Role |
|---|---|---|---|---|---|---|
| Nginx Reverse Proxy | pandya-nginx | 172.24.0.2 | 80/443 | 80/443 | pandya-proxy-network | Entry Point |

---

## 8. AWS ECS Task Assignments (Phase 6)

| Task Name | Subnet | IP Range | Count | CPU | Memory | Role |
|---|---|---|---|---|---|---|
| ml-iris-knn | ml-subnet (10.0.1.0/24) | 10.0.1.x | 2-4 | 256 units | 512 MB | ML Service |
| ml-housing | ml-subnet (10.0.1.0/24) | 10.0.1.x | 1-2 | 256 units | 512 MB | ML Service |
| dl-lstm | dl-subnet (10.0.2.0/24) | 10.0.2.x | 1-2 | 512 units | 1024 MB | DL Service |
| dl-cnn | dl-subnet (10.0.2.0/24) | 10.0.2.x | 1-2 | 512 units | 1024 MB | DL Service |
| nlp-sentiment | nlp-subnet (10.0.3.0/24) | 10.0.3.x | 1-2 | 256 units | 512 MB | NLP Service |
| nlp-ner | nlp-subnet (10.0.3.0/24) | 10.0.3.x | 1-2 | 256 units | 512 MB | NLP Service |
| agentic-planner | agentic-subnet (10.0.4.0/24) | 10.0.4.x | 1-2 | 512 units | 1024 MB | Agentic Service |
| agentic-o1 | agentic-subnet (10.0.4.0/24) | 10.0.4.x | 1-2 | 512 units | 1024 MB | Agentic Service |

---

## 9. AWS Managed Services (Phase 6)

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

## 10. CIDR Range Summary & Conflict Analysis

| Range | Usage | Status | Conflicts | Notes |
|---|---|---|---|---|
| 172.17.0.0/16 | Docker default bridge | In Use | None | Already in use, DO NOT use |
| 172.18.0.0/16 | Available | Available | None | Can use if needed in future |
| 172.19.0.0/16 | Available | Available | None | Can use if needed in future |
| 172.20.0.0/24 | ml-network (NAS) | Allocated | None | ✅ Safe, verified |
| 172.21.0.0/24 | dl-network (NAS) | Allocated | None | ✅ Safe, verified |
| 172.22.0.0/24 | nlp-network (NAS) | Allocated | None | ✅ Safe, verified |
| 172.23.0.0/24 | agentic-network (NAS) | Allocated | None | ✅ Safe, verified |
| 172.24.0.0/24 | pandya-proxy-network (NAS) | Allocated | None | ✅ Safe, verified |
| 192.168.x.x | Synology NAS Management | In Use | None | NAS LAN, no Docker conflict |
| 10.0.0.0/16 | AWS VPC | Allocated | None | ✅ AWS standard, no NAS conflict |
| 10.0.1.0/24 | ml-subnet (AWS) | Allocated | None | ✅ Safe for AWS |
| 10.0.2.0/24 | dl-subnet (AWS) | Allocated | None | ✅ Safe for AWS |
| 10.0.3.0/24 | nlp-subnet (AWS) | Allocated | None | ✅ Safe for AWS |
| 10.0.4.0/24 | agentic-subnet (AWS) | Allocated | None | ✅ Safe for AWS |
| 10.0.100.0/24 | Public subnet (AWS) | Allocated | None | ✅ ALB, NAT Gateway |

---

## 11. Network Isolation Matrix (NAS)

| From → To | ml-network | dl-network | nlp-network | agentic-network | pandya-proxy-network | External |
|---|---|---|---|---|---|---|
| ml-network | ✅ Direct | ❌ Via Nginx | ❌ Via Nginx | ❌ Via Nginx | ✅ Reverse Proxy | ✅ Via Nginx |
| dl-network | ❌ Via Nginx | ✅ Direct | ❌ Via Nginx | ❌ Via Nginx | ✅ Reverse Proxy | ✅ Via Nginx |
| nlp-network | ❌ Via Nginx | ❌ Via Nginx | ✅ Direct | ❌ Via Nginx | ✅ Reverse Proxy | ✅ Via Nginx |
| agentic-network | ❌ Via Nginx | ❌ Via Nginx | ❌ Via Nginx | ✅ Direct | ✅ Reverse Proxy | ✅ Via Nginx |
| pandya-proxy-network | ✅ Upstream | ✅ Upstream | ✅ Upstream | ✅ Upstream | ✅ Direct | ✅ Port 80/443 |
| External | ❌ No direct | ❌ No direct | ❌ No direct | ❌ No direct | ✅ Port 80/443 | N/A |

---

## 12. Docker Compose IPAM Configuration Template

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

---

## 13. Migration Path: NAS → AWS

| Phase | Environment | CIDR Range | Services | Status |
|---|---|---|---|---|
| Phase 1-5 | NAS (Synology Docker) | 172.20-24/24 | All 4 domains (8 projects) | Development |
| Phase 6 Early | NAS (stays online) | 172.20-24/24 | Fallback/dev copy | Parallel |
| Phase 6 Middle | AWS (new deployment) | 10.0.x/24 | All 4 domains (8 projects) | Staging |
| Phase 6 Late | AWS (production) | 10.0.x/24 | All 4 domains (8 projects) | Production |
| Phase 6 Final | NAS (dev only) | 172.20-24/24 | Reduced workload | Dev/Fallback |

---

## 14. DNS & Routing Summary

| Environment | Domain | Entry Point | Protocol | Target | IP/Port |
|---|---|---|---|---|---|
| NAS | pandyahomelab.com | Nginx | HTTP/HTTPS | pandya-nginx | 172.24.0.2:80/443 |
| NAS | /ml/* | Nginx Upstream | HTTP (internal) | ml-iris-knn | 172.20.0.10:8000 |
| NAS | /dl/* | Nginx Upstream | HTTP (internal) | dl-lstm | 172.21.0.10:8000 |
| NAS | /nlp/* | Nginx Upstream | HTTP (internal) | nlp-sentiment | 172.22.0.10:8000 |
| NAS | /agentic/* | Nginx Upstream | HTTP (internal) | agentic-planner | 172.23.0.10:8000 |
| AWS | pandyahomelab.com | ALB | HTTPS | ALB DNS | ALB IP |
| AWS | /ml/* | ALB Target Group | HTTP (internal) | ml-iris-knn ECS | 10.0.1.x:8000 |
| AWS | /dl/* | ALB Target Group | HTTP (internal) | dl-lstm ECS | 10.0.2.x:8000 |
| AWS | /nlp/* | ALB Target Group | HTTP (internal) | nlp-sentiment ECS | 10.0.3.x:8000 |
| AWS | /agentic/* | ALB Target Group | HTTP (internal) | agentic-planner ECS | 10.0.4.x:8000 |

---

## 15. Quick Reference: IP Address Allocation Scheme

```
NAS DOCKER NETWORKS:
172.20.0.x    - ML Domain
  .1 = Gateway
  .2 = PostgreSQL
  .3 = MinIO
  .4 = Redis
  .5 = MLflow
  .10-19 = Project Services (ml-iris-knn, ml-housing, etc.)

172.21.0.x    - DL Domain
  .1 = Gateway
  .2 = PostgreSQL
  .3 = MinIO
  .4 = Redis
  .5 = MLflow
  .10-19 = Project Services

172.22.0.x    - NLP Domain
  .1 = Gateway
  .2 = PostgreSQL
  .3 = MinIO
  .4 = Redis
  .5 = MLflow
  .10-19 = Project Services

172.23.0.x    - Agentic Domain
  .1 = Gateway
  .2 = PostgreSQL
  .3 = MinIO
  .4 = Redis
  .5 = MLflow
  .10-19 = Project Services

172.24.0.x    - Proxy Network
  .1 = Gateway
  .2 = Nginx

AWS VPC SUBNETS:
10.0.1.x      - ml-subnet (private)
10.0.2.x      - dl-subnet (private)
10.0.3.x      - nlp-subnet (private)
10.0.4.x      - agentic-subnet (private)
10.0.100.x    - Public subnet (ALB, NAT)
```

---

## 16. Verification Checklist

- [x] NAS Docker networks verified (172.17.0.0/16 is only Docker default in use)
- [x] No conflicts with Synology management network (192.168.x.x)
- [x] AWS VPC CIDR (10.0.0.0/16) doesn't conflict with NAS (172.x.x.x)
- [x] Site-to-site VPN possible between NAS and AWS (different ranges)
- [x] Each domain has isolated network (no cross-network direct access)
- [x] Nginx is sole entry point from internet
- [x] All infrastructure services (postgres, minio, redis, mlflow) isolated per domain
- [x] Project services can only reach other services via Nginx routing

---

**Status: READY FOR IMPLEMENTATION** ✅

All network ranges allocated, verified, and documented. Safe to proceed with Phase 1a.
