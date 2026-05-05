---
title: Internet Access from NAS & Domain Routing
status: Proposed (new)
context: |
  ADR-016 establishes 5 isolated Docker networks per the topology. However, traffic flows and
  routing rules are not yet specified. Nginx must:
  
  1. Accept external traffic on ports 80/443
  2. Route to correct domain based on URL path (/ml/*, /dl/*, etc.)
  3. Connect to internal services on private domain networks
  4. Support both NAS and AWS deployments with identical routing logic
decision: |
  Nginx reverse proxy sits on pandya-proxy-network (public, exposed to host on 80/443).
  Routes defined by URL path prefix per ADR-003 (URL hierarchy):
  
  - /ml/*       → upstream ml-iris-knn:8000 (172.20.0.10)
  - /dl/*       → upstream dl-lstm:8000 (172.21.0.10)
  - /nlp/*      → upstream nlp-sentiment:8000 (172.22.0.10)
  - /agentic/*  → upstream agentic-planner:8000 (172.23.0.10)
  - /health     → Nginx local response (200 OK)
  - /            → Static landing page (website index.html)
  
  Nginx configuration is stateless, identical between NAS and AWS. At AWS, upstream IPs
  are replaced with ECS service discovery names, but routing logic unchanged.
alternatives_considered: |
  A. Subdomain-based routing (ml.pandyahomelab.com, dl.pandyahomelab.com) — rejected, requires
     wildcard DNS, more complex certificates, doesn't align with portfolio narrative
  B. Port-based routing (8100 for ml, 8200 for dl, etc.) — rejected, requires port discovery,
     harder to explain externally
  C. Path-based routing (chosen) — simple, intuitive, single certificate, aligns with URL hierarchy ADR-003
consequences: |
  Positive:
  - Single certificate (*.pandyahomelab.com or www.pandyahomelab.com)
  - URL structure aligns with business logic (/ml/ shows ML projects)
  - Works identically on NAS and AWS (just change upstream targets)
  - Easy to debug (curl http://localhost/ml/health to check ml domain is up)
  - Future API gateway can add per-domain middleware (auth, rate limits)
  
  Negative:
  - Nginx must know all upstreams in advance (no dynamic routing)
  - If project service down, Nginx returns 502; requires health checks
  
  Mitigations:
  - Each project service implements GET /health endpoint
  - Nginx upstream includes max_fails/fail_timeout for automatic failover
  - Grafana dashboard shows per-upstream health
related_adrs: |
  - ADR-003 — URL hierarchy (path-based routing aligns with /ml/*, /dl/*, etc.)
  - ADR-016 — Domain-level network topology (Nginx on public network, upstreams on private)
  - ADR-015 — Deployment service separation (Nginx config in deployment/nginx/)
---

# ADR-019 — Internet Access from NAS & Domain Routing

**Status:** Proposed (new)  
**Date:** May 2026  
**Author:** Archit Pandya

## Context

ADR-016 defines the network topology: 5 Docker networks, each isolated, with Nginx as public entry point. But the routing rules—how traffic actually reaches the right service—are not yet specified.

**Routing requirements:**
1. External users access `https://pandyahomelab.com/ml/iris-knn` and reach the ml-iris-knn service
2. External users access `https://pandyahomelab.com/dl/lstm-forecast` and reach the dl-lstm service
3. Internal services on private networks (postgres, minio, etc.) remain completely private
4. Nginx health/status endpoints available for monitoring
5. Configuration identical between NAS (development) and AWS (production)

## Decision

**Nginx reverse proxy** routes traffic by **URL path prefix**. Each domain has a dedicated upstream block pointing to the primary project service in that domain's network.

### Nginx Configuration Template

```nginx
# deployment/nginx/nginx.conf
upstream ml_projects {
    # NAS: direct IP
    server ml-iris-knn:8000 max_fails=3 fail_timeout=30s;
    # AWS: ECS service discovery name (same syntax, different resolution)
}

upstream dl_projects {
    server dl-lstm:8000 max_fails=3 fail_timeout=30s;
}

upstream nlp_projects {
    server nlp-sentiment:8000 max_fails=3 fail_timeout=30s;
}

upstream agentic_projects {
    server agentic-planner:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    listen 443 ssl;
    server_name pandyahomelab.com www.pandyahomelab.com;

    # SSL certificates (managed by external cert provider, e.g., Let's Encrypt)
    ssl_certificate /etc/nginx/certs/pandyahomelab.crt;
    ssl_certificate_key /etc/nginx/certs/pandyahomelab.key;

    # Redirect HTTP to HTTPS
    if ($scheme != "https") {
        return 301 https://$server_name$request_uri;
    }

    # Health check endpoint (Nginx local, no upstream)
    location /health {
        access_log off;
        return 200 "OK\n";
        add_header Content-Type text/plain;
    }

    # Landing page (static or redirects to root)
    location / {
        root /var/www/html;
        try_files $uri $uri/ /index.html;
    }

    # ML domain routes
    location /ml/ {
        proxy_pass http://ml_projects;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Path $request_uri;
        proxy_set_header X-Domain ml;
    }

    # DL domain routes
    location /dl/ {
        proxy_pass http://dl_projects;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Path $request_uri;
        proxy_set_header X-Domain dl;
    }

    # NLP domain routes
    location /nlp/ {
        proxy_pass http://nlp_projects;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Path $request_uri;
        proxy_set_header X-Domain nlp;
    }

    # Agentic domain routes
    location /agentic/ {
        proxy_pass http://agentic_projects;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Path $request_uri;
        proxy_set_header X-Domain agentic;
    }

    # Catch-all (404)
    location ~ ^/(?!ml/|dl/|nlp/|agentic/|health|$|index.html) {
        return 404;
    }
}
```

### Service Discovery — NAS vs AWS

**NAS (Synology Docker):**
```
/ml/*       → ml-iris-knn:8000    (container hostname, resolved via Docker DNS to 172.20.0.10)
/dl/*       → dl-lstm:8000        (container hostname, resolved via Docker DNS to 172.21.0.10)
/nlp/*      → nlp-sentiment:8000  (container hostname, resolved via Docker DNS to 172.22.0.10)
/agentic/*  → agentic-planner:8000 (container hostname, resolved via Docker DNS to 172.23.0.10)
```

**AWS (ECS service discovery):**
```
/ml/*       → ml-iris-knn.service.local:8000   (ECS service discovery DNS)
/dl/*       → dl-lstm.service.local:8000
/nlp/*      → nlp-sentiment.service.local:8000
/agentic/*  → agentic-planner.service.local:8000
```

Same upstream names, different resolution mechanism. Configuration identical.

### Health Check Endpoints

Each project service must implement:

```python
# Every project: presentation-logic/api/routes.py
@router.get("/health")
async def health_check():
    """Liveness probe for Kubernetes/Docker health checks."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }
```

Nginx checks: `curl http://ml-iris-knn:8000/health` every 10s (configurable).

### Request Flow (Detailed)

```
1. User: https://pandyahomelab.com/ml/iris-knn
   ↓
2. DNS resolves pandyahomelab.com → NAS IP or AWS ALB IP
   ↓
3. TLS/HTTPS connection established
   ↓
4. Nginx receives request
   ├─ Path matches /ml/
   ├─ Upstream group: ml_projects
   ├─ Select server: ml-iris-knn:8000 (or use round-robin if multiple servers)
   ↓
5. Nginx connects to ml-iris-knn container on ml-network
   ├─ Sends: GET /iris-knn HTTP/1.1 (path rewrite may apply)
   ├─ Headers include: X-Real-IP, X-Forwarded-For, X-Domain=ml
   ↓
6. ml-iris-knn processes request
   ├─ Calls ml-postgres:5432 for data (same network, direct)
   ├─ Calls ml-minio:9000 for artifacts (same network, direct)
   ├─ Returns response
   ↓
7. Nginx sends response to user
   ↓
8. User sees response from ml-iris-knn project
```

### What Does NOT Go Through Nginx

```
PostgreSQL (5432)      — NO, internal to ml-network
MinIO (9000)           — NO, internal to ml-network
Redis (6379)           — NO, internal to ml-network
MLflow (5000)          — NO, internal to ml-network
Cross-domain requests  — YES, must go through Nginx (/ml/ calls /dl/ → redirected to Nginx)
```

### Logging & Observability

Nginx logs all incoming requests:

```
2026-05-05T10:15:23Z | POST /ml/iris-knn/predict | 200 | 45ms | client=192.168.1.100 | upstream=ml-iris-knn:8000
2026-05-05T10:15:24Z | GET /dl/lstm/history | 200 | 123ms | client=192.168.1.100 | upstream=dl-lstm:8000
2026-05-05T10:15:25Z | GET /nlp/sentiment/status | 503 | 1000ms | client=192.168.1.100 | upstream=nlp-sentiment:8000 (UNHEALTHY)
```

In Grafana:
- Per-upstream response time (ml vs dl vs nlp vs agentic)
- Error rate by domain
- Request count by path
- Upstream health status

### Migration: NAS to AWS

**NAS Nginx config:**
```nginx
upstream ml_projects {
    server ml-iris-knn:8000;
}
```

**AWS Nginx config (in ALB, or self-hosted):**
```nginx
upstream ml_projects {
    server ml-iris-knn.service.local:8000;  # ECS service discovery
}
```

Everything else identical. Routing logic unchanged.

## Alternatives Considered

### A. Subdomain-based routing (ml.pandyahomelab.com)
**Rejected** — Requires:
- Wildcard DNS records
- Wildcard SSL certificate (or multi-SAN cert)
- More complex certificate renewal
- Not aligned with single-domain portfolio narrative

### B. Port-based routing (ml on 8100, dl on 8200)
**Rejected** — Requires:
- Multiple port exposures to host
- Port discovery mechanism
- Harder to explain externally ("why port 8100?")
- Not aligned with API design best practices

### C. Path-based routing (chosen)
**Accepted** — Single certificate, intuitive URL structure, aligns with ADR-003, works on NAS and AWS identically.

## Consequences

### Positive
- **Single certificate** — One TLS cert for `pandyahomelab.com`, covers all domains
- **Standard URL hierarchy** — `/ml/`, `/dl/`, `/nlp/`, `/agentic/` matches business logic
- **Identical config NAS→AWS** — Change only upstream targets, keep routing rules
- **Easy debugging** — `curl http://localhost/ml/health` confirms ml domain health
- **Future-proof** — Can add per-domain rate limiting, authentication middleware in Nginx
- **Clear observability** — Nginx access logs show which domain served each request

### Negative
- **Nginx must know all upstreams** — Requires manual config update if new primary service added
- **Single point of failure** — Nginx goes down, entire platform is unreachable (mitigated by container restart policy)
- **TLS termination overhead** — Nginx consumes ~50MB RAM for SSL/TLS operations

### Mitigations
- **Automated restart:** Docker restart policy `unless-stopped` ensures Nginx restarts on crash
- **Health checks:** Nginx monitors each upstream, removes unhealthy servers from rotation
- **Monitoring:** Grafana alerts if Nginx is down or high error rate
- **Config validation:** Every config change validated with `nginx -t` before deployment

## Implementation Checklist

- [ ] Create `deployment/nginx/` folder
- [ ] Write `deployment/nginx/nginx.conf` per template above
- [ ] Create `deployment/nginx/Dockerfile` (builds nginx image)
- [ ] Write `deployment/nginx/ssl/` folder for certificates (initially use self-signed for NAS)
- [ ] Create `website/index.html` with domain buttons (landing page)
- [ ] Add `pandya-proxy-network` to `docker-compose.yml`
- [ ] Add Nginx service to compose with port mappings 80:80, 443:443
- [ ] Test: `curl http://localhost/health` → should return 200 OK
- [ ] Test: `curl http://localhost/ml/health` → should return 503 (ml domain not up yet)
- [ ] Document: `/docs/runbooks/nginx-routing.md` (troubleshooting guide)

## Related ADRs

- **ADR-003** — URL hierarchy (routing aligns with /ml/*, /dl/*, etc.)
- **ADR-016** — Domain-level network topology (Nginx on public network, upstreams on private)
- **ADR-015** — Deployment service separation (Nginx config in deployment/)

---

**Status: READY FOR IMPLEMENTATION**

Nginx configuration provides transparent routing from external traffic to internal domain networks.
Next step: Phase 1a execution (build ml-iris-knn project and verify /ml/health returns 200).
