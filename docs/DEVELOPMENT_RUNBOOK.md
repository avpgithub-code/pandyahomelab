# pandyaHomeLab — Development Runbook

**Version:** 1.0 (Phase 1a lessons learned)  
**Last Updated:** May 2026  
**Purpose:** Reference for all future ML/DL/NLP/Agentic project development.  
Captures every hard-won lesson from Phase 1a so Phase 1b+ is clean first time.

---

## 1. Infrastructure Overview

### 1.1 What's Already Running (Never Recreate)

| Service | Container | IP | Host Port | Notes |
|---|---|---|---|---|
| PostgreSQL | ml-postgres | 172.20.0.2 | 5433 | DSM has native postgres on 5432 — use 5433 |
| MinIO | ml-minio | 172.20.0.3 | 9000/9001 | Object storage + console |
| Redis | ml-redis | 172.20.0.4 | 6379 | Cache |
| MLflow | ml-mlflow | 172.20.0.5 | 5000 | Currently restarting — non-critical for Phase 1b |
| Nginx | pandya-nginx | 172.24.0.2 (proxy) / 172.20.0.20 (ml) | 8080/8443 | Reverse proxy entry point |

### 1.2 Port Allocation — NEVER USE THESE

| Port | Occupied By | Why |
|---|---|---|
| 80, 443 | DSM native Nginx | Verizon ISP blocks 80/443 for residential anyway |
| 5432 | DSM native PostgreSQL | Always use 5433 for ml-postgres |
| 5500, 5501 | DSM web UI | Internal DSM ports |
| 5443 | DSM native Nginx HTTPS | |
| 6379 | ml-redis | |
| 8080, 8443 | pandya-nginx | |
| 9000, 9001 | ml-minio | |
| 8001 | ml-iris-knn | Phase 1a project |

### 1.3 Available Ports for New Projects

| Project | Assigned Port | IP |
|---|---|---|
| ml-iris-knn | 8001 | 172.20.0.10 |
| ml-housing-linear | 8002 | 172.20.0.11 |
| ml-random-forest | 8003 | 172.20.0.12 |
| dl-lstm | 8010 | 172.21.0.10 |
| nlp-sentiment | 8020 | 172.22.0.10 |
| agentic-claude | 8030 | 172.23.0.10 |

---

## 2. Network Topology (ADR-016)

### 2.1 Docker Networks

```
Internet
    ↓
Cloudflare Tunnel (HTTPS, noTLSVerify: true)
    ↓
pandya-nginx (172.24.0.2 on proxy-network, 172.20.0.20 on ml-network)
    ↓
ml-iris-knn (172.20.0.10) | ml-housing-linear (172.20.0.11) | ...
```

### 2.2 Network Names

| Network | CIDR | Docker Name | Gateway |
|---|---|---|---|
| ML domain | 172.20.0.0/24 | ml_ml-network | 172.20.0.1 |
| DL domain | 172.21.0.0/24 | dl_dl-network | 172.21.0.1 |
| NLP domain | 172.22.0.0/24 | nlp_nlp-network | 172.22.0.1 |
| Agentic domain | 172.23.0.0/24 | agentic_ag-network | 172.23.0.1 |
| Proxy | 172.24.0.0/24 | nginx_pandya-proxy-network | 172.24.0.1 |

### 2.3 IP Allocation Rules (ADR-016)

```
.1   = Gateway
.2   = PostgreSQL
.3   = MinIO
.4   = Redis
.5   = MLflow
.10  = Project 1 (e.g., ml-iris-knn)
.11  = Project 2 (e.g., ml-housing-linear)
.12  = Project 3
.20  = Nginx (when attached to domain network)
```

---

## 3. HTTP Request Flow — End to End

```
Browser → https://pandyahomelab.com/ml/iris-knn/
    ↓
Cloudflare Edge (DNS: pandyahomelab.com → tunnel CNAME)
    ↓
cloudflared (running on NAS, connects to Cloudflare)
    ↓
https://localhost:8443 (Nginx, self-signed cert, noTLSVerify)
    ↓
Nginx strips /ml/iris-knn/ prefix → proxy_pass http://ml_projects/
    ↓
ml-iris-knn:8000 (FastAPI, on ml-network 172.20.0.10)
    ↓
Response back up the chain
```

### 3.1 Nginx Routing Rules

```nginx
# PATTERN: Each project gets its own sub-path
location /ml/iris-knn/ {
    proxy_pass http://ml_projects/;   # trailing slash strips prefix
}

location /ml/housing-linear/ {
    proxy_pass http://ml_housing/;    # new upstream for Phase 1b
}

# Domain root returns listing JSON
location = /ml/ {
    return 200 '{"domain":"ml","projects":["iris-knn","housing-linear"]}';
}

# Undeployed domains return 503
location /dl/ {
    return 503 '{"status":"coming_soon","domain":"dl"}';
}
```

---

## 4. Known Issues & Solutions

### 4.1 Port Conflicts

| Problem | Solution |
|---|---|
| `bind: address already in use` on 5432 | DSM postgres owns 5432 — map ml-postgres to 5433 |
| `bind: address already in use` on 80/443 | DSM nginx owns 80/443 — use 8080/8443 for our Nginx |
| Nginx container exits with "host not found in upstream" | Future domain upstreams don't exist yet — return 503 instead |

### 4.2 Docker Patterns

```dockerfile
# ✅ CORRECT: Install system-wide (not --user)
RUN pip install --no-cache-dir -r requirements.txt

# ❌ WRONG: --user causes permission denied when running as appuser
RUN pip install --user --no-cache-dir -r requirements.txt

# ✅ CORRECT: Copy from builder to system locations
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# ✅ CORRECT: Healthcheck without curl (not in slim image)
HEALTHCHECK CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# ❌ WRONG: curl not available in python:3.11-slim
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
```

### 4.3 Python 3.8 Compatibility (NAS system Python)

```python
# ✅ CORRECT for Python 3.8
from typing import Optional, List, Tuple
def func(x: Optional[str] = None): ...

# ❌ WRONG: Python 3.10+ only
def func(x: str | None = None): ...

# ✅ CORRECT: Pydantic v2 validator
from pydantic import field_validator
@field_validator("data")

# ⚠️ DEPRECATED (works but warns): Pydantic v1 style
from pydantic import validator
@validator("data")
```

### 4.4 Python Import Path (Hyphenated Folders)

```bash
# Folder names use hyphens (ADR convention)
# Python can't import from hyphenated names
# Solution: create symlinks at project root

ln -s db-logic db_logic
ln -s application-logic application_logic
ln -s presentation-logic presentation_logic

# Add to conftest.py for tests:
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

### 4.5 Docker Compose Environment Variables

```bash
# ✅ CORRECT: create .env file (auto-loaded by docker-compose ps)
cp .env.local .env

# ⚠️ WARNING: --env-file flag only works with up/down, not ps
sudo docker-compose --env-file .env.local up -d   # works
sudo docker-compose ps                             # shows warnings without .env
```

### 4.6 Cloudflare Tunnel

```yaml
# ✅ CORRECT config (~/.cloudflared/config.yml)
ingress:
  - hostname: pandyahomelab.com
    service: https://localhost:8443
    originRequest:
      noTLSVerify: true   # required for self-signed cert

# ❌ WRONG: causes redirect loop (HTTP → HTTPS → Cloudflare → loop)
    service: http://localhost:8080
```

```bash
# ✅ CORRECT: start tunnel (survives session disconnect)
nohup cloudflared tunnel run pandya-homelab >> ~/cloudflared.log 2>&1 &

# ❌ WRONG: killed when terminal closes
cloudflared tunnel run pandya-homelab &
```

---

## 5. New Project Checklist (Phase 1b+)

For every new project, follow this checklist:

### 5.1 Pre-Development
- [ ] Assign port (next available: 8002 for ml-housing)
- [ ] Assign IP (next available: 172.20.0.11 for ml-housing)
- [ ] Verify no port conflicts: `sudo netstat -tlnp | grep <port>`
- [ ] Confirm ML infrastructure is running: `sudo docker-compose ps` in deployment/ml/

### 5.2 Project Scaffolding
- [ ] Create feature branch: `git checkout -b ml-housing-linear/scaffold`
- [ ] Copy template: `cp -r ml/_templates/ml-project-template/ ml/ml-housing-linear/`
- [ ] Update pyproject.toml: name, version, description
- [ ] Update README.md: project title and overview
- [ ] Update CHANGELOG.md: v1.0.0-alpha1 entry
- [ ] Create symlinks: `ln -s db-logic db_logic` etc.

### 5.3 Development
- [ ] Add dataset to `data/` (force-add if .gitignore blocks: `git add -f data/`)
- [ ] Implement db-logic: loader + preprocessor
- [ ] Implement application-logic: model + service
- [ ] Implement presentation-logic: routes + schemas + ui.html
- [ ] All imports use underscore names (db_logic, not db-logic)
- [ ] Use `Optional[str]` not `str | None` (Python 3.8 on NAS)
- [ ] fetch() in ui.html uses full path: `/ml/housing-linear/predict`

### 5.4 Testing (TIER 1)
```bash
python3 -m pytest tests/ -v
# Expected: all tests passing
```

### 5.5 Docker Build (TIER 2)
```bash
sudo docker build -f docker/Dockerfile -t ml-housing-linear:latest .
sudo docker run -d -p 8002:8000 --name ml-housing-linear ml-housing-linear:latest
sleep 15
curl http://localhost:8002/health
sudo docker stop ml-housing-linear && sudo docker rm ml-housing-linear
```

### 5.6 Integration (TIER 3)
```bash
# Add to docker-compose.dev.yml (port 8002, IP 172.20.0.11)
# Add upstream to nginx.conf
# Add /ml/housing-linear/ location block
# Rebuild Nginx: docker-compose down && docker build && docker-compose up -d
# Test: curl -k https://localhost:8443/ml/housing-linear/health
```

### 5.7 Nginx Update Pattern
```bash
# 1. Add upstream in nginx.conf
upstream ml_housing {
    server ml-housing-linear:8000 max_fails=3 fail_timeout=30s;
}

# 2. Add location block
location /ml/housing-linear/ {
    proxy_pass http://ml_housing/;
    ...
}

# 3. Update /ml/ listing
location = /ml/ {
    return 200 '{"domain":"ml","projects":["iris-knn","housing-linear"]}';
}

# 4. Rebuild Nginx
cd deployment/nginx/
sudo docker-compose down
sudo docker build -t pandya-nginx:latest .
sudo docker-compose up -d

# 5. Connect Nginx to ml-network (already done — no change needed)
```

### 5.8 Commit & Tag
```bash
git add .
git commit -m "feat(ml-housing-linear): implement housing price regression"
git checkout main
git merge --ff-only ml-housing-linear/scaffold
git tag v.ml-housing-linear-1.0.0
```

---

## 6. Docker Compose Startup Order

When starting fresh after NAS reboot:

```bash
# Step 1: ML infrastructure
cd /volume1/pandya-homelab/deployment/ml/
sudo docker-compose up -d
sleep 20

# Step 2: ML projects
sudo docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Step 3: Nginx
cd /volume1/pandya-homelab/deployment/nginx/
sudo docker-compose up -d

# Step 4: Cloudflare tunnel
nohup cloudflared tunnel run pandya-homelab >> ~/cloudflared.log 2>&1 &
```

---

## 7. Useful Diagnostic Commands

```bash
# Check all running containers
sudo docker ps

# Check container networks and IPs
sudo docker inspect <container> --format '{{range $net, $conf := .NetworkSettings.Networks}}{{$net}}: {{$conf.IPAddress}}{{"\n"}}{{end}}'

# Check port usage
sudo netstat -tlnp | grep <port>

# Check Nginx routing
curl -k https://localhost:8443/health
curl -k https://localhost:8443/ml/iris-knn/health

# Check cloudflared
ps aux | grep cloudflared | grep -v grep
tail -20 ~/cloudflared.log

# Purge Cloudflare cache (when page not updating)
# Cloudflare Dashboard → Caching → Purge Everything
```
